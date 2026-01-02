# GB-Link Pro - Pi Zero Game Boy Link Cable Interface

Play Game Boy games online using a Raspberry Pi Zero 2W as a link cable bridge to the internet.

Cross platform client of online Tetris DMG and Pokemon trading to the PiZero2W for a standalone experience. No longer need a separate computer and adapter connected over USB. CLI menu is the only option at this time.

## Features

- **Online Multiplayer** - Connect your Game Boy to online servers for multiplayer gaming
- **GBA Multiboot** - Load ROMs onto GBA without a flash cart
- **Extensible** - Potential to add support for additional games


## Currently Supported Games

### Tetris
- Tetris DMG (EN)

### Pokémon Trading

### Generation 1
- Pokémon Red, Blue, Yellow (EN/JP)

### Generation 2  
- Pokémon Gold, Silver, Crystal (EN/JP)

### Generation 3
- Pokémon Ruby, Sapphire, Emerald, FireRed, LeafGreen
- Requires GBA multiboot ROM


## Hardware Requirements

- Raspberry Pi Zero 2W (or compatible Pi with SPI)
- Game Boy / GBC / GBA with compatible game
- Level shifter (see below)

## Hardware Connection

The Raspberry Pi operates at **3.3V** logic while the Game Boy uses **5V**. You **must** use a level shifter when connecting to a GB/GBC game (even on a GBA) to avoid damaging your Pi.

### Options:
1. **Adapter board/HAT** - A pre-made board with level shifters built in (can use GB-Link USB adapter board)
2. **Manual wiring** - Wire level shifters (e.g., TXS0108E, BSS138-based modules) inline between the Pi and link cable

### Wiring (BCM Pin Numbers)

Connect through your level shifter:

| Pi Side (3.3V)   | BCM GPIO | Physical Pin | ↔ | Link Cable (5V) |
|------------------|----------|--------------|---|-----------------|
| SPI MOSI         | GPIO 10  | Pin 19       | ↔ | SO (Serial Out) |
| SPI MISO         | GPIO 9   | Pin 21       | ↔ | SI (Serial In)  |
| SPI SCLK         | GPIO 11  | Pin 23       | ↔ | SC (Clock)      |
| Chip Select (SD) | GPIO 8   | Pin 24       | ↔ | SD
| Ground           | GND      | Pin 6, etc   | — | GND             |

## Installation

```bash
# Install system dependencies
sudo apt update
sudo apt install python3-pip python3-spidev

# Install Python packages (spidev, RPi.GPIO, websockets)
pip3 install -r requirements.txt

# Enable SPI
sudo raspi-config  # Interface Options -> SPI -> Enable

# Compile GBA multiboot (optional, for Gen 3)
gcc -o gba_multiboot_spidev gba_multiboot_spidev.c
```

## Usage

```bash
# Run the main menu

chmod +x cli_menu.sh

./cli_menu.sh

# Or run directly
python3 pokemon_main.py  # Pokémon trading
python3 tetris_main.py   # Online Tetris

```
To send multiboot directly to GBA (or any other multiboot ROM), use the following command:
```bash
./gba_multiboot_spidev pokemon_gen3_to_genx_mb.gba
```
## Trading using Gen3 games

The software currently makes use of the Pokemon-Gen3-to-GenX project to add support to trading using Pokémon Ruby/Sapphire/Emerald/Fire Red/Leaf Green.

As such, you must first multiboot into it using the multiboot option. Then, you can select the Gen 3 option to trade.

## License

MIT License for everything except gba_multiboot_spidev.c, which is licensed CC0.

## Credits
gba_multiboot_spidev.c is heavily derrived from the implementation at https://github.com/akkera102/gba_03_multiboot, which is licensed CC0. (Found at https://github.com/maciel310/gba-mmo-proxy)

Original usb adapter project by stacksmashing bringing tetris online
https://github.com/stacksmashing/gb-tetris-web

Fork of tetris web client by classictoni with best of 7 games option
https://github.com/classictoni/gb-tetris-web

Original Pokemon trading client and server by Lorenzooone. Pokemon client logic is unmodified from this project and clients are cross compatible.
https://github.com/Lorenzooone/PokemonGB_Online_Trades

Multiboot homebrew by Lorenzooone to allow for Gen3 trading
https://github.com/Lorenzooone/Pokemon-Gen3-to-Gen-X
