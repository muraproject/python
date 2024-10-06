import string

# Kamus untuk encoding
CHARS = string.ascii_letters + string.digits + ' .,:;!?'
CHAR_TO_INDEX = {char: i for i, char in enumerate(CHARS)}
INDEX_TO_CHAR = {i: char for i, char in enumerate(CHARS)}

def compress(data):
    compressed = ""
    for i in range(0, len(data), 2):
        char1 = data[i]
        char2 = data[i+1] if i+1 < len(data) else ' '  # Pad with space if odd
        
        if char1 in CHAR_TO_INDEX and char2 in CHAR_TO_INDEX:
            # Encode two characters into one
            encoded = CHAR_TO_INDEX[char1] * len(CHARS) + CHAR_TO_INDEX[char2]
            compressed += chr(encoded + 32)  # Shift to printable ASCII range
        else:
            # If characters not in our set, keep them as is
            compressed += f"({char1}{char2})"
    
    return compressed

def decompress(compressed):
    decompressed = ""
    i = 0
    while i < len(compressed):
        char = compressed[i]
        if char == '(':
            # Handle uncompressed pair
            decompressed += compressed[i+1:i+3]
            i += 4
        elif 32 <= ord(char) < 32 + len(CHARS)**2:
            # Decode one character back to two
            encoded = ord(char) - 32
            index1, index2 = divmod(encoded, len(CHARS))
            decompressed += INDEX_TO_CHAR[index1] + INDEX_TO_CHAR[index2]
            i += 1
        else:
            # Unexpected character, add as is
            decompressed += char
            i += 1
    
    return decompressed.rstrip()  # Remove potential padding

# Test dengan tepat 100 karakter
def hapus_50_karakter_pertama(text):
    return text[50:]

test_100 = "This is a test string that is exactly one hundred characters long. It includes numbers like 12345 too!"

compressed_100 = compress(test_100)
test_150 = "11111111111111111111111111111111111111111111111112" + compressed_100
compressed_150 = compress(test_150)
test_200 = "11111111111111111111111111111111111111111111111112" + compressed_150
compressed_200 = compress(test_200)
tampung100= ""+compressed_100
compressed1002= compress(tampung100)

# decompressed_100 = decompress(compressed_100)
decompressed_200 = decompress(compressed_200)
decompressed_150 = decompress(hapus_50_karakter_pertama(decompressed_200))
decompressed_100 = decompress(hapus_50_karakter_pertama(decompressed_150))
# print(f"Original 100 chars   : {test_100}")
# print(f"Compressed  ({len(compressed_100)} chars): {compressed_100}")
# print(f"Decompressed         : {decompressed_100}")
# print(f"Compression ratio: {len(compressed_100) / len(test_100):.2f}")
# print(f"Original == Decompressed: {test_100 == decompressed_100}")
# print(test_150)
# print(compressed_150)
# print(decompressed_150)
# print(hapus_50_karakter_pertama(decompressed_150))
# print(decompressed_100)
print(f"Compressed  ({len(compressed1002)} chars)")