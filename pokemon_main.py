import os
import signal
import sys
import traceback
import time

sys.path.append('utilities')

from utilities.gsc_trading import GSCTrading
from utilities.gsc_trading_jp import GSCTradingJP
from utilities.rby_trading import RBYTrading
from utilities.rby_trading_jp import RBYTradingJP
from utilities.rse_sp_trading import RSESPTrading
from utilities.websocket_client import PoolTradeRunner, ProxyConnectionRunner
from utilities.gsc_trading_menu import GSCTradingMenu
from utilities.gsc_trading_strings import GSCTradingStrings

MULTIBOOT_GBA_PATH = "pokemon_gen3_to_genx_mb.gba"

def main():
    """Main entry point that runs the user menu and selects the correct function."""
    menu = GSCTradingMenu(kill_function)
    menu.handle_menu()

    link_hardware = None
    try:
        # Dynamically load the correct hardware driver based on the menu choice
        if menu.multiboot:
            run_multiboot(MULTIBOOT_GBA_PATH)
            return  # Multiboot doesn't need cleanup
        else:
            from utilities.gb_link_lowlevel import GBLinkLow
            link_hardware = GBLinkLow()
            run_regular_trade(link_hardware, menu)
    except Exception as e:
        print(f"An error occurred in main: {e}")
        traceback.print_exc()
    finally:
        if link_hardware:
            link_hardware.deinit()

def run_multiboot(file_path):
    """Sends a ROM to GBA via multiboot using the C program."""
    import subprocess
    
    print("\n--- GBA Multiboot Sender ---")
    
    # Path to the compiled C multiboot program
    multiboot_exe = os.path.join(os.path.dirname(__file__), "gba_multiboot_spidev")
    
    if not os.path.exists(multiboot_exe):
        print(f"Error: {multiboot_exe} not found!")
        print("Please compile it first:")
        print("  gcc -o gba_multiboot_spidev gba_multiboot_spidev.c")
        return
    
    if not os.path.exists(file_path):
        print(f"Error: ROM file {file_path} not found!")
        return
    
    try:
        # Call the C program with sudo (needed for SPI access)
        result = subprocess.run(
            ["sudo", multiboot_exe, file_path],
            check=True,
            text=True
        )
        
        if result.returncode == 0:
            print("\n✓ Multiboot completed successfully!")
            print("The GBA should now be running the Gen 3 trading ROM.")
            print("You can now select Gen 3 trading from the main menu.")
        
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Multiboot failed with error code {e.returncode}")
    except FileNotFoundError:
        print("\n✗ Error: Could not execute multiboot program")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")

def run_regular_trade(link_hardware, menu):
    """Handles all non-multiboot trading sessions."""
    last_trade_response = 0
    def trade_sender(data, num_bytes):
        nonlocal last_trade_response
        last_trade_response = link_hardware.xfer(data, num_bytes)
    def trade_receiver(num_bytes):
        return last_trade_response
    def trade_list_sender(data_list, chunk_size):
        link_hardware.xfer_list(data_list)
    TradeClass = None
    pre_sleep = False
    link_hardware.set_mode(3)
    if menu.gen == 2:
        TradeClass = GSCTradingJP if menu.japanese else GSCTrading
    elif menu.gen == 3:
        TradeClass = RSESPTrading
        pre_sleep = True
    elif menu.gen == 1:
        TradeClass = RBYTradingJP if menu.japanese else RBYTrading
    if not TradeClass:
        print("Invalid generation selected.")
        return
    connection_thread = None
    if menu.trade_type == GSCTradingStrings.two_player_trade_str:
        connection_thread = ProxyConnectionRunner(menu, kill_function)
    else:
        connection_thread = PoolTradeRunner(menu, kill_function)
    trade_logic = TradeClass(trade_sender, trade_receiver, connection_thread, menu, kill_function, pre_sleep)
    connection_thread.start()
    if menu.trade_type == GSCTradingStrings.two_player_trade_str:
        trade_logic.player_trade(menu.buffered)
    else:
        trade_logic.pool_trade()

def kill_function():
    os._exit(1)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s, f: os._exit(1))
    try:
        main()
    except Exception:
        traceback.print_exc()
    print("Pokémon session finished.")
