/*
 * GBA Multiboot using spidev (found at gba-mmo-proxy) original repo offline
 * 
 * Compile: gcc -o gba_multiboot_spidev gba_multiboot_spidev.c
 * Usage: ./gba_multiboot_spidev pokemon_gen3_to_genx_mb.gba
 */

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <linux/spi/spidev.h>

static int spi_fd;

//---------------------------------------------------------------------------
uint32_t Spi32(uint32_t val)
{
    uint8_t tx[4], rx[4];
    
    // Big endian (same as bswap_32)
    tx[0] = (val >> 24) & 0xFF;
    tx[1] = (val >> 16) & 0xFF;
    tx[2] = (val >> 8) & 0xFF;
    tx[3] = val & 0xFF;
    
    struct spi_ioc_transfer tr = {
        .tx_buf = (unsigned long)tx,
        .rx_buf = (unsigned long)rx,
        .len = 4,
        .speed_hz = 1000000,  // 1MHz like original
        .delay_usecs = 0,
        .bits_per_word = 8,
        .cs_change = 0,
    };
    
    if (ioctl(spi_fd, SPI_IOC_MESSAGE(1), &tr) < 0) {
        perror("SPI transfer failed");
        return 0;
    }
    
    // Convert response (big endian)
    uint32_t result = (rx[0] << 24) | (rx[1] << 16) | (rx[2] << 8) | rx[3];
    return result;
}

//---------------------------------------------------------------------------
void multiboot(const char *filename)
{
    // Open SPI device
    spi_fd = open("/dev/spidev0.0", O_RDWR);
    if (spi_fd < 0) {
        perror("Failed to open SPI device");
        exit(1);
    }
    
    // Configure SPI - Mode 3, 1MHz
    uint8_t mode = SPI_MODE_3;
    uint8_t bits = 8;
    uint32_t speed = 1000000;
    
    if (ioctl(spi_fd, SPI_IOC_WR_MODE, &mode) < 0 ||
        ioctl(spi_fd, SPI_IOC_WR_BITS_PER_WORD, &bits) < 0 ||
        ioctl(spi_fd, SPI_IOC_WR_MAX_SPEED_HZ, &speed) < 0) {
        perror("Failed to configure SPI");
        close(spi_fd);
        exit(1);
    }
    
    printf("SPI configured: Mode 3, 1MHz\n");

    // -----------------------------------------------------
    // get filesize
    int fd = open(filename, O_RDONLY);

    if(fd == -1)
    {
        fprintf(stderr, "Error opening game ROM: fopen\n");
        exit(1);
    }

    struct stat stbuf;

    if(fstat(fd, &stbuf) == -1)
    {
        fprintf(stderr, "Error opening game ROM: fstat\n");
        exit(1);
    }

    uint32_t fsize = stbuf.st_size;

    if(fsize > 0x40000)
    {
        fprintf(stderr, "File size Error Max 256KB\n");
        exit(1);
    }

    close(fd);


    // -----------------------------------------------------
    // read file
    FILE* fp = fopen(filename, "rb");

    if(fp == NULL)
    {
        fprintf(stderr, "Error opening game ROM: Fopen Error\n");
        exit(1);
    }

    uint8_t* fdata = calloc(fsize + 0x10, sizeof(uint8_t));

    if(fdata == NULL)
    {
        fprintf(stderr, "Error opening game ROM: Calloc Error\n");
        exit(1);
    }

    fread(fdata, 1, fsize, fp);
    fclose(fp);


    // -----------------------------------------------------
    printf("Waiting for GBA. Please make sure the link cable is connected and turn on your GBA.\n");

    uint32_t recv;

    do
    {
        recv = Spi32(0x6202) >> 16;
        usleep(10000);  // 10ms delay (NOT 36µs!)

    } while(recv != 0x7202);

    printf("Handshake successful!\n");

    // -----------------------------------------------------
    Spi32(0x6102);

    uint16_t* fdata16 = (uint16_t*)fdata;

    for(uint32_t i=0; i<0xC0; i+=2)
    {
        Spi32(fdata16[i / 2]);
    }

    Spi32(0x6200);


    // -----------------------------------------------------
    Spi32(0x6202);
    Spi32(0x63D1);

    uint32_t token = Spi32(0x63D1);

    if((token >> 24) != 0x73)
    {
        fprintf(stderr, "Failed handshake!\n");
        exit(1);
    }


    uint32_t crcA, crcB, crcC, seed;

    crcA = (token >> 16) & 0xFF;
    seed = 0xFFFF00D1 | (crcA << 8);
    crcA = (crcA + 0xF) & 0xFF;

    Spi32(0x6400 | crcA);

    fsize +=  0xF;
    fsize &= ~0xF;

    token = Spi32((fsize - 0x190) / 4);
    crcB  = (token >> 16) & 0xFF;
    crcC  = 0xC387;

    // -----------------------------------------------------
    printf("Sending data (%d bytes)...\n", fsize);
    uint32_t* fdata32 = (uint32_t*)fdata;

    for(uint32_t i=0xC0; i<fsize; i+=4)
    {
        uint32_t dat = fdata32[i / 4];

        // crc step
        uint32_t tmp = dat;

        for(uint32_t b=0; b<32; b++)
        {
            uint32_t bit = (crcC ^ tmp) & 1;

            crcC = (crcC >> 1) ^ (bit ? 0xc37b : 0);
            tmp >>= 1;
        }

        // encrypt step
        seed = seed * 0x6F646573 + 1;
        dat = seed ^ dat ^ (0xFE000000 - i) ^ 0x43202F2F;

        // send
        uint32_t chk = Spi32(dat) >> 16;

        if(chk != (i & 0xFFFF))
        {
            fprintf(stderr, "Transmission error at byte %u: chk == %08x\n", i, chk);
            exit(1);
        }
        
        // Progress indicator
        if((i % 4096) == 0) {
            printf("  Sent %u / %u bytes (%.1f%%)\r", i, fsize, (i * 100.0) / fsize);
            fflush(stdout);
        }
    }
    printf("\nData sent successfully!\n");

    // crc step final
    uint32_t tmp = 0xFFFF0000 | (crcB << 8) | crcA;

    for(uint32_t b=0; b<32; b++)
    {
        uint32_t bit = (crcC ^ tmp) & 1;

        crcC = (crcC >> 1) ^ (bit ? 0xc37b : 0);
        tmp >>= 1;
    }


    // -----------------------------------------------------
    printf("Waiting for GBA acknowledgment...\n");
    Spi32(0x0065);

    do
    {
        recv = Spi32(0x0065) >> 16;
        usleep(10000);  // 10ms delay

    } while(recv != 0x0075);

    Spi32(0x0066);
    uint32_t crcGBA = Spi32(crcC & 0xFFFF) >> 16;

    printf("\n\nLoading complete!\n");

    usleep(1000000);  // 1 second

    free(fdata);
    close(spi_fd);
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <rom_file.gba>\n", argv[0]);
        return 1;
    }
    
    printf("GBA Multiboot (spidev version)\n");
    printf("ROM: %s\n\n", argv[1]);
    
    multiboot(argv[1]);
    
    return 0;
}
