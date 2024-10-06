import string
import random

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

# Membuat string acak 1000 karakter
random_string = ''.join(random.choice(CHARS) for _ in range(1000))

# Mengambil 100 karakter pertama
first_100 = random_string[:100]

# Kompresi
compressed_100 = compress(first_100)

# Dekompresi (untuk verifikasi)
decompressed_100 = decompress(compressed_100)

print(f"Original 1000 chars: {random_string[:50]}...{random_string[-50:]}")
print(f"First 100 chars   : {first_100}")
print(f"Compressed ({len(compressed_100)} chars): {compressed_100}")
print(f"Decompressed      : {decompressed_100}")
print(f"Compression ratio: {len(compressed_100) / len(first_100):.2f}")
print(f"Original == Decompressed: {first_100 == decompressed_100}")