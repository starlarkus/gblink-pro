import time
import asyncio
import json
import websockets
from asyncio import Queue, Lock, Event

# Constants
CMD_MASTER_READY = 0x29; RESP_READY = 0x55; CMD_START_A = 0x60; CMD_START_B = 0x79;
CMD_GO_1 = 0x30; CMD_ZERO = 0x00; CMD_POLL = 0x02; CMD_FINAL = 0x43;
MUSIC_NEXT = 0x50; WIN_CODE = 0xAA; LOSE_CODE = 0x77; GB_WIN = 0x77;
GB_LOSE = 0xAA; GB_FILL_DONE = 0xFF;

# Music selection bytes
MUSIC_A = 0x1C
MUSIC_B = 0x1D
MUSIC_C = 0x1E
MUSIC_OFF = 0x1F

def hex_to_bytes(val):
    """Converts a hex string to a bytes object."""
    if not val: return b""
    if not isinstance(val, str):
        try: return bytes(val)
        except TypeError: return b""
    s = val.strip()
    if len(s) % 2: s = "0" + s
    try: return bytes([int(s[i:i+2], 16) for i in range(0, len(s), 2)])
    except (ValueError, TypeError): return b""

def is_first_game(users):
    """Checks if any user has wins, determining if it's the first game."""
    return not any(int(u.get("num_wins", 0)) > 0 for u in users)

class TetrisLink:
    def __init__(self, link_low):
        self.link = link_low
        self.link.set_mode(3)
        self.opponent_height = 0
        self.pico_uuid = None
        self.latest_users = []
        self.garbage_data = b""
        self.game_over_event = Event()
        self.gb_tx_queue = Queue()
        self.gb_rx_queue = Queue()
        self.in_match = False
        self.link_lock = Lock()

    async def run(self, ws, host_mode):
        """Main entry point to start all concurrent tasks for a Tetris match."""
        print("WebSocket connected!")
        await ws.send(json.dumps({"type": "register", "name": "PiZero_Player"}))
        
        server_listener = asyncio.create_task(self._server_listener_loop(ws))
        io_task = asyncio.create_task(self._gb_io_loop())
        rx_task = asyncio.create_task(self._gb_rx_processor_loop(ws))
        
        print("Waiting for lobby information from server...")
        while not self.pico_uuid:
            await asyncio.sleep(0.05)
        
        try:
            if host_mode:
                await self._host_game_loop(ws)
            else:
                await self._join_game_loop(ws)
        finally:
            # Cleanly shut down all tasks when the game loop ends
            server_listener.cancel()
            io_task.cancel()
            rx_task.cancel()

    async def _host_game_loop(self, ws):
        """Loop for the host player, allowing them to start rounds."""
        while True:
            self.game_over_event.clear()
            input("Press Enter to start the round...")
            await ws.send(json.dumps({"type": "start"}))
            await self.game_over_event.wait()
            print("Round finished. Ready for host to start next round.")

    async def _join_game_loop(self, ws):
        """Loop for the joining player, waiting for the host to start rounds."""
        print("Waiting for host to start the game...")
        while True:
            self.game_over_event.clear()
            await self.game_over_event.wait()
            print("Round finished. Waiting for host to start next round.")

    async def _server_listener_loop(self, ws):
        """Listens for and processes messages from the WebSocket server."""
        lobby_code_printed = False
        while True:
            try:
                msg = await ws.recv()
                if not msg: continue
                data = json.loads(msg)
                msg_type = data.get("type")
                
                if msg_type != "game_info": print(f"[Server] Received: {msg_type}")

                if msg_type == "user_info": self.pico_uuid = data.get("uuid")
                elif msg_type == "game_info":
                    self.latest_users = data.get("users", [])
                    self._update_opponent_height()
                    if not self.in_match and not lobby_code_printed and data.get("name"):
                        print(f"\n==== LOBBY CODE: {data['name']} ====\n")
                        lobby_code_printed = True
                elif msg_type == "garbage": self.garbage_data = hex_to_bytes(data.get("garbage"))
                elif msg_type == "lines": await self.gb_tx_queue.put(data.get("lines", 0) & 0xFF)
                elif msg_type == "win" or msg_type == "reached_30_lines": await self.end_match_from_server(won=True)
                elif msg_type == "dead": await self.end_match_from_server(won=False)
                elif msg_type == "error":
                    print(f"[Server] Error: {data.get('msg', 'Lobby error')}")
                    if self.in_match: await self.end_match_from_server(won=False)
                    break
                elif msg_type == "start_game":
                    print("[Game] Starting new match...")
                    self.in_match = True
                    tiles = hex_to_bytes(data.get("tiles"))
                    await self.start_game_sequence(tiles, self.garbage_data, is_first_game(self.latest_users))
            except Exception as e:
                print(f"Server listener error: {e}")
                if self.in_match: await self.end_match_from_server(won=False)
                break

    def _update_opponent_height(self):
        """Calculates the max height of all opponents in the lobby."""
        heights = [u.get("height", 0) for u in self.latest_users if u.get("uuid") != self.pico_uuid]
        self.opponent_height = max(heights) if heights else 0

    async def handshake(self, max_seconds=7):
        """Performs the initial handshake with the Game Boy."""
        print("[GB] Attempting handshake...")
        start_time = time.monotonic()
        while (time.monotonic() - start_time) < max_seconds:
            try:
                # Send the ready command and get the response
                received_byte = self.link.xfer_byte(CMD_MASTER_READY)
                
                # Check if the response is what we expect
                if received_byte == RESP_READY:
                    print("[GB] Handshake SUCCESS!")
                    return True
                
                # Debug print to show what we are actually receiving
                print(f"[GB] Handshake attempt: Sent 0x{CMD_MASTER_READY:02X}, Received 0x{received_byte:02X}")

            except Exception as e:
                # Catch potential hardware errors from xfer_byte
                print(f"[GB] Hardware error during handshake: {e}")

            await asyncio.sleep(0.1)
            
        print("[GB] Handshake FAILED (timed out).")
        return False
    
    def send_music(self, music_byte, count=5):
        """Sends music selection byte to Game Boy multiple times (for preview)."""
        for _ in range(count):
            self.link.xfer_byte(music_byte)
            time.sleep(0.1)
    
    def confirm_music(self):
        """Sends MUSIC_NEXT (0x50) to confirm music selection and move to handicap screen."""
        self.link.xfer_byte(MUSIC_NEXT)
        time.sleep(0.1)
    
    def complete_handicap_phase(self, count=5):
        """Sends zeros to pass through the handicap selection screen."""
        for _ in range(count):
            self.link.xfer_byte(CMD_ZERO)
            time.sleep(0.1)
        
    async def prepare_after_handshake(self, music_choice=MUSIC_A):
        """Legacy function - use send_music, confirm_music, complete_handicap_phase instead."""
        print("[GB] Preparing menus...")
        for _ in range(3): self.link.xfer_byte(music_choice); await asyncio.sleep(0.1)
        self.link.xfer_byte(MUSIC_NEXT); await asyncio.sleep(0.1)
        for _ in range(2): self.link.xfer_byte(CMD_ZERO); await asyncio.sleep(0.1)
        print("[GB] Ready for match start.")
        
    async def start_game_sequence(self, tiles_bytes, garbage_bytes, is_first_game: bool):
        """Sends the specific byte sequence to start a match on the Game Boy."""
        print("[GB] Starting game sequence...")
        if is_first_game:
            self.link.xfer_byte(CMD_START_A); time.sleep(0.15)
            self.link.xfer_byte(CMD_MASTER_READY); time.sleep(0.004)
        else:
            self.link.xfer_byte(CMD_START_A); time.sleep(0.07)
            for _ in range(3): self.link.xfer_byte(CMD_POLL); time.sleep(0.07)
            self.link.xfer_byte(CMD_START_B); time.sleep(0.33)
            self.link.xfer_byte(CMD_START_A); time.sleep(0.15)
            self.link.xfer_byte(CMD_MASTER_READY); time.sleep(0.07)
        for byte in garbage_bytes: self.link.xfer_byte(byte); time.sleep(0.004)
        self.link.xfer_byte(CMD_MASTER_READY); time.sleep(0.008)
        for byte in tiles_bytes: self.link.xfer_byte(byte); time.sleep(0.004)
        for b in (CMD_GO_1, CMD_ZERO, CMD_POLL, CMD_POLL, 0x20):
            self.link.xfer_byte(b); time.sleep(0.07)
        print("[GB] Game started!")

    async def end_match_from_server(self, won):
        """Forces the match to end from the server's perspective."""
        if not self.in_match: return
        
        sequence = (WIN_CODE, CMD_POLL, CMD_POLL, CMD_POLL, CMD_FINAL) if won else \
                   (LOSE_CODE, CMD_POLL, CMD_POLL, CMD_POLL, CMD_FINAL)
        for b in sequence:
            self.gb_tx_queue.put_nowait(b)
            
        print("[GB] Sending force-end sequence...")
        while not self.gb_tx_queue.empty():
            await asyncio.sleep(0.1)
        print("[GB] Force-end sequence sent.")

        print(f"[Game] Match ended by server. Player {'WON' if won else 'LOST'}.")
        self.in_match = False
        self.game_over_event.set()

    async def _gb_io_loop(self):
        """The main loop for exchanging data with the Game Boy during a match."""
        try:
            while True:
                if not self.in_match:
                    await asyncio.sleep(0.02)
                    continue
                
                byte_to_send = self.opponent_height
                if not self.gb_tx_queue.empty():
                    byte_to_send = self.gb_tx_queue.get_nowait()
                
                async with self.link_lock:
                    received_byte = self.link.xfer_byte(byte_to_send)
                
                await self.gb_rx_queue.put(received_byte)
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass
        finally:
            print("[GB] IO loop stopped.")

    async def _gb_rx_processor_loop(self, ws):
        """Processes bytes received from the Game Boy and sends updates to the server."""
        try:
            while True:
                rx = await self.gb_rx_queue.get()
                if not self.in_match:
                    continue
                
                if rx < 0x14:  # Player's current stack height
                    await ws.send(json.dumps({"type": "update", "height": rx}))
                elif 0x80 <= rx <= 0x85:  # Lines cleared
                    await ws.send(json.dumps({"type": "lines", "lines": rx}))
                elif rx == GB_WIN:  # Player won (cleared 30 lines)
                    await ws.send(json.dumps({"type": "win"}))
                    await self.end_match_from_server(won=True)
                elif rx == GB_LOSE: # Player topped out (animation starting)
                    await ws.send(json.dumps({"type": "dead"}))
                elif rx == GB_FILL_DONE: # Player's top-out animation finished
                    print("[Game] Match ended. Player LOST (by top-out).")
                    self.in_match = False
                    
                    print("[GB] Sending finalization command...")
                    async with self.link_lock:
                        self.link.xfer_byte(CMD_FINAL)
                        time.sleep(0.01)
                    print("[GB] Finalization command sent.")
                    
                    self.game_over_event.set()
        except asyncio.CancelledError:
            pass
        finally:
            print("[GB] RX processor loop stopped.")
