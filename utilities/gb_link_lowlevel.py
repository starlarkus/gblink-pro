import spidev
import RPi.GPIO as GPIO

# This class provides the low-level hardware interface for the Game Boy link port
# using a Raspberry Pi's SPI and GPIO pins.

class GBLinkLow:
    def __init__(self):
        """Initializes the SPI device and GPIO pins."""
        self.pin_sd = 8

        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        
        # Configure SPI mode and speed.
        self.spi.mode = 0b11 # SPI Mode 3
        self.spi.max_speed_hz = 500000
        
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin_sd, GPIO.OUT)
        GPIO.output(self.pin_sd, GPIO.LOW)
        
        print(f"GBLinkLow Initialized. SPI Mode: {self.spi.mode}, Speed: {self.spi.max_speed_hz} Hz")

    def set_mode(self, mode: int):
        """
        Compatibility function for existing scripts. The SPI mode is fixed
        during initialization in this hardware version.
        """
        print(f"SPI Mode confirmed: {self.spi.mode}")

    def xfer_byte(self, out_b: int) -> int:
        """Transfers a single byte to and from the Game Boy simultaneously."""
        response = self.spi.xfer2([out_b])
        return response[0]

    def xfer(self, data_to_send: int, num_bytes: int) -> int:
        """Transfers an integer of a specified number of bytes."""
        tx_bytes = data_to_send.to_bytes(num_bytes, 'big')
        rx_bytes = self.spi.xfer2(list(tx_bytes))
        return int.from_bytes(bytearray(rx_bytes), 'big')

    def xfer_list(self, out_list: list):
        """Transfers a list of bytes using hardware SPI."""
        self.spi.xfer2(out_list)
        
    def xfer_u32(self, out_data: int) -> int:
        """This function is for GBA multiboot and is not used by GB/GBC protocols."""
        raise NotImplementedError("xfer_u32 is not supported in this driver.")
        
    def deinit(self):
        """Closes the SPI connection and cleans up GPIO resources."""
        self.spi.close()
        GPIO.output(self.pin_sd, GPIO.HIGH)
        GPIO.cleanup()
        print("GBLinkLow shut down.")
