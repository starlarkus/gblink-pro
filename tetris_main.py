import asyncio
import sys
from argparse import ArgumentParser
sys.path.append('utilities')

from utilities.gb_link_lowlevel import GBLinkLow
from utilities.tetris_link import TetrisLink, MUSIC_A, MUSIC_B, MUSIC_C, MUSIC_OFF, MUSIC_NEXT
import websockets
import time

DEFAULT_SERVER = "wss://tetrisserver.gblink.io:443"

# Music options mapping
MUSIC_OPTIONS = {
    'a': MUSIC_A,
    'b': MUSIC_B,
    'c': MUSIC_C,
    'off': MUSIC_OFF,
    'o': MUSIC_OFF,
}

async def main(server_url):
    link = None
    try:
        if not check_internet():
            return

        link = GBLinkLow()
        
        # Interactive menu with server option
        while True:
            print(f"\nCurrent server: {server_url}")
            print("(h) Host a match")
            print("(j) Join a match")
            print("(s) Change server")
            mode_choice = input("Select option: ").strip().lower()
            
            if mode_choice == 's':
                new_server = input(f"Enter server URL [{server_url}]: ").strip()
                if new_server:
                    server_url = new_server
                continue
            elif mode_choice in ('h', 'j'):
                break
            else:
                print("Invalid option. Please try again.")
        
        host_mode = (mode_choice == 'h')
        lobby_code = None
        if not host_mode:
            lobby_code = input("Enter 4-letter lobby code: ").strip()

        tetris = TetrisLink(link)
        if not await tetris.handshake():
            print("Could not handshake with Game Boy.")
            return
        
        # Send Music A immediately to get the Game Boy music menu started
        music_names = {'a': 'A', 'b': 'B', 'c': 'C', 'o': 'OFF'}
        current_music = 'a'
        print("\n[GB] Starting music selection...")
        tetris.send_music(MUSIC_A)
        
        print("\nSelect music (press Enter to confirm, or type a/b/c/o to change):")
        print(f"Currently playing: Music A")
        
        while True:
            choice = input("Music [Enter=confirm]: ").strip().lower()
            
            if choice == '':
                # Enter pressed - confirm current selection
                print(f"Music {music_names[current_music]} confirmed!")
                break
            elif choice in MUSIC_OPTIONS:
                # New selection - send to Game Boy
                current_music = choice
                tetris.send_music(MUSIC_OPTIONS[choice])
                print(f"Playing Music {music_names[choice]}... Press Enter to confirm.")
            else:
                print("Invalid option. Use a/b/c/o or Enter to confirm.")
        
        # Move past music selection screen (sends 0x50)
        print("[GB] Confirming music selection...")
        tetris.confirm_music()
        
        # Move past handicap selection screen (sends zeros)
        print("[GB] Passing handicap screen...")
        tetris.complete_handicap_phase()

        path = "/create" if host_mode else f"/join/{lobby_code.upper()}"
        full_url = server_url + path
        
        print(f"Connecting to WebSocket at {full_url}...")
        async with websockets.connect(full_url) as ws:
            await tetris.run(ws, host_mode)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if link:
            link.deinit()
        print("Tetris session finished.")


def check_internet():
    import socket
    print("Checking for internet connection...")
    try:
        host = socket.gethostbyname("www.google.com")
        s = socket.create_connection((host, 80), 2)
        s.close()
        return True
    except Exception:
        print("No internet connection.")
        return False

if __name__ == "__main__":
    parser = ArgumentParser(description="Tetris online client")
    parser.add_argument("-s", "--server", dest="server_url", default=DEFAULT_SERVER,
                        help=f"WebSocket server URL (default: {DEFAULT_SERVER})")
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args.server_url))
    except KeyboardInterrupt:
        print("\nProgram interrupted.")
