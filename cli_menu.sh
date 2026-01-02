#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"

while true; do
    echo ""
    echo "==== Pi Zero GB Link Menu ===="
    echo "1) Play Online Tetris"
    echo "2) Trade Pokémon Online"
    echo "3) Exit"
    read -p "Select option: " choice

    case $choice in
        1)
            echo "Starting Tetris client..."
            # Run the Tetris asyncio script
            sudo python3 tetris_main.py
            ;;
        2)
            echo "Starting Pokémon client..."
            # Run the Pokémon synchronous script
            sudo python3 pokemon_main.py
            ;;
        3)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid option. Please try again."
            ;;
    esac
done
