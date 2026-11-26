import numpy as np

class BitStream:
    def __init__(self, ifile : str, ofile : str):
        self.ofp = open(ofile, "wb")
        self.ifp = np.fromfile(ifile, dtype=np.uint8)
        self.input_size:np.uint32 = np.uint32(self.ifp.size)
        self.__readed_byte: np.uint8 = np.uint8(0)
        self.__eof: bool = False
        self.__count_unreaded_bits_from_byte: np.uint8 = np.uint8(0)
        self.__count_writed_bits_to_byte: np.uint8 = np.uint8(0)
        self.__byte_to_write: np.uint8 = np.uint8(0)
        self.size:np.uint32 = self.input_size
        self.output_size: np.uint32 = np.uint32(0)
        self.cur: np.uint32 = np.uint32(0)

    def read_size(self)->np.uint:
        self.cur = 4
        self.size = self.ifp[:4].view(np.uint32)[0]

        return self.size

    def write_size(self):
        self.ofp.write(self.input_size.tobytes())

    def read_bit(self) -> np.uint8:

        if(self.__count_unreaded_bits_from_byte == 0):
            if not self.__eof:
                self.__readed_byte = self.read_byte()
                self.__count_unreaded_bits_from_byte = np.uint8(8)
            else:
                return 0
        self.__count_unreaded_bits_from_byte -= np.uint8(1)
        bit = (self.__readed_byte & 0x80) >> 7
        self.__readed_byte <<= 1
        return np.uint8(bit)

    def write_bit(self, bit : np.uint8):
        if(self.__count_writed_bits_to_byte < 8):
            self.__byte_to_write <<= np.uint8(1)
            self.__byte_to_write |= bit
            self.__count_writed_bits_to_byte += np.uint8(1)
            if(self.__count_writed_bits_to_byte == 8):
                self.write_byte(np.uint8(self.__byte_to_write))
                self.__byte_to_write = np.uint8(0)
                self.__count_writed_bits_to_byte = np.uint8(0)

    def read_byte(self) -> np.uint8:

        if self.cur < self.input_size:
            self.__readed_byte = self.ifp[self.cur]
            self.cur += 1

            return self.__readed_byte
        self.__eof = True
        return 0

    def write_byte(self, byte : np.uint8):
        self.output_size += 1
        self.ofp.write(byte.tobytes())

    def close(self):
        if(self.__count_writed_bits_to_byte != 0):
            self.__byte_to_write <<= np.uint8(8 - self.__count_writed_bits_to_byte)
            self.ofp.write(np.uint8(self.__byte_to_write).tobytes())
        self.ofp.close()

    def EOF(self) ->bool:
        return self.__eof

    def BitsPlusFollow(self, bit: np.uint8, bits_to_follow: np.uint):
        self.write_bit(bit)
        while(bits_to_follow > 0):
            self.write_bit(not bit)
            bits_to_follow -= 1

class FrequencyTable:
    def __init__(self, table=None):
        if table is None:
            table = np.ones(256, dtype=np.int64)
        self.table = table.astype(np.int64)
        self.b = np.zeros(257, dtype=np.int64)
        self.size = int(self.table.sum())
        self.high: np.uint = 0x100000000 - 1
        self.bits_high: np.uint8 = 32
        if self.size >= 0x40000000:
            self.bits_high = 40
            self.high = (1 << self.bits_high) - 1
        self.aggressiveness: np.uint = 5000
        self.generate_probability()
        self.lim: np.uint = self.aggressiveness*50

    def generate_probability(self):
        self.delitel = self.size
        self.b[1:] = np.cumsum(self.table)

    def update(self, byte : np.uint8):
        self.size += self.aggressiveness
        self.table[byte] += self.aggressiveness

        if self.table[byte] >= self.lim:
            self.cut_table()
        self.generate_probability()

    def cut_table(self):
        for i in range(self.table.size):
            if self.table[i] > 1:
                self.table[i] //= 2
        self.size = int(self.table.sum())

    def getProbability(self, index: np.uint):
        return int(self.b[int(index)+1])

    def getElem(self, index: np.uint8) -> bytes:
        return index.tobytes()

class ArithmeticCompressor:
    def __init__(self, bitstream : BitStream, frequency_table : FrequencyTable):
        self.bitstream = bitstream
        self.frequency_table = frequency_table
        self.high = self.frequency_table.high
        self.bits_high = self.frequency_table.bits_high
        self.first_qtr:np.uint = (self.high + 1)//4
        self.half:np.uint = 2*self.first_qtr
        self.third_qtr:np.uint = 3*self.first_qtr
        self.bits_to_follow: int = 0

        self.value = 0

    def init_encoding(self):
        self.h = np.zeros(int(self.bitstream.size)+1, dtype=np.int64)
        self.h[0] = self.high
        self.l = np.zeros(int(self.bitstream.size)+1, dtype=np.int64)
        self.i: int = 0

    def encode_byte(self, byte : np.uint8):
        j = int(byte)
        self.i += 1

        l_prev = int(self.l[self.i-1])
        h_prev = int(self.h[self.i-1])
        diff_prev = h_prev - l_prev + 1

        self.l[self.i] = l_prev + self.frequency_table.getProbability(j-1) * diff_prev // self.frequency_table.delitel
        self.h[self.i] = l_prev + self.frequency_table.getProbability(j) * diff_prev // self.frequency_table.delitel - 1

        li = self.l[self.i]
        hi = self.h[self.i]

        while True:
            if hi < self.half:
                self.bitstream.BitsPlusFollow(0, self.bits_to_follow)
                self.bits_to_follow = 0
            elif li >= self.half:
                self.bitstream.BitsPlusFollow(1, self.bits_to_follow)
                self.bits_to_follow = 0
                li -= self.half
                hi -= self.half
            elif li >= self.first_qtr and hi < self.third_qtr:
                self.bits_to_follow += 1
                li -= self.first_qtr
                hi -= self.first_qtr
            else:
                break

            li += li
            hi += hi + 1
        self.l[self.i] = li
        self.h[self.i] = hi

    def init_decoding(self, factor: np.uint8):
        if self.bitstream.cur == 0:
            self.bitstream.read_size()
        self.init_encoding()
        factor //= 8
        self.value = 0
        for _ in range(factor):
            self.value *= 0x100
            self.value += int(self.bitstream.read_byte())

    def decode_byte(self) -> np.uint8:
        self.i += 1

        l_prev = int(self.l[self.i-1])
        h_prev = int(self.h[self.i-1])
        diff_prev = h_prev - l_prev + 1

        freq = ((self.value - l_prev + 1) * self.frequency_table.delitel - 1) // diff_prev
        j = 0
        while self.frequency_table.b[j+1] <= freq:
            j += 1

        self.l[self.i] = l_prev + self.frequency_table.getProbability(j-1) * diff_prev // self.frequency_table.delitel
        self.h[self.i] = l_prev + self.frequency_table.getProbability(j) * diff_prev // self.frequency_table.delitel - 1

        li = self.l[self.i]
        hi = self.h[self.i]

        while True:
            if hi < self.half:
                pass
            elif li >= self.half:
                delta = self.half
                li -= delta
                hi -= delta
                self.value -= delta
            elif li >= self.first_qtr and hi < self.third_qtr:
                delta = self.first_qtr
                li -= delta
                hi -= delta
                self.value -= delta
            else:
                break

            li += li
            hi += hi + 1
            self.value += self.value + int(self.bitstream.read_bit())

        self.l[self.i] = li
        self.h[self.i] = hi

        return np.uint8(j)

def compress_ari(ifile : str, ofile : str):
    bitStream = BitStream(ifile, ofile)
    bitStream.write_size()
    FreqTable = FrequencyTable(np.bincount(bitStream.ifp, minlength=256))
    bitStream.ofp.write(FreqTable.table.astype(np.uint32).tobytes())

    AC = ArithmeticCompressor(bitStream, FreqTable)
    AC.init_encoding()
    while(not AC.bitstream.EOF()):
        c = AC.bitstream.read_byte()
        if AC.bitstream.EOF():
            AC.bitstream.BitsPlusFollow(1, AC.bits_to_follow)
            break
        AC.encode_byte(c)

    AC.bitstream.close()

def decompress_ari(ifile : str, ofile : str):
    bitStream = BitStream(ifile, ofile)
    bitStream.read_size()
    table = bitStream.ifp[4:4+256*4].view(np.uint32)
    bitStream.cur += 256*4
    FreqTable = FrequencyTable(table)

    AC = ArithmeticCompressor(bitStream, FreqTable)

    AC.init_decoding(AC.bits_high)
    while(AC.bitstream.size > AC.bitstream.output_size):
        c = AC.decode_byte()
        AC.bitstream.write_byte(c)
    AC.bitstream.close()
