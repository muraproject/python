import base64

def compress_to_50(data):
    data_bytes = data.encode('utf-8')
    padded_data = data_bytes.ljust(50, b'\0')[:50]
    base64_encoded = base64.b64encode(padded_data).decode('ascii')
    return base64_encoded[:50]

def decompress_from_50(compressed):
    padded = compressed.ljust(68, '=')
    decoded = base64.b64decode(padded)
    return decoded.decode('utf-8').rstrip('\0')

full_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum. Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo. Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit, sed quia non numquam eius modi tempora incidunt ut labore et dolore magnam aliquam quaerat voluptatem. Ut enim ad minima veniam, quis nostrum exercitationem ullam corporis suscipit laboriosam, nisi ut aliquid ex ea commodi consequatur? Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla pariatur? At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis praesentium voluptatum deleniti atque corrupti quos dolores et quas molestias excepturi sint occaecati cupiditate non provident, similique sunt in culpa qui officia deserunt mollitia animi, id est laborum et dolorum fuga. Et harum quidem rerum facilis est et expedita distinctio."

def partition_text(text):
    first_100 = text[:100]
    remaining = text[100:]
    parts = [remaining[i:i+50] for i in range(0, len(remaining), 50)]
    return first_100, parts

first_100, partitioned = partition_text(full_text)

# Kompresi
compressed_parts = []
compressed_ku = compress_to_50(first_100[:50])
compressed_parts.append(compressed_ku)

for part in partitioned:
    decompressed = decompress_from_50(compressed_ku)
    test_ku = decompressed + part
    compressed_ku = compress_to_50(test_ku[-50:])
    compressed_parts.append(compressed_ku)

# Output
print("Original Text:")
print(full_text)
print(f"\nLength of original text: {len(full_text)}")

print("\nFull Compressed Text:")
print(' '.join(compressed_parts))
print(f"Length of full compressed text: {len(' '.join(compressed_parts))}")

# Dekompresi
decompressed_full = ''
for comp_part in compressed_parts:
    decompressed_full += decompress_from_50(comp_part)

print("\nFull Decompressed Text:")
print(decompressed_full)
print(f"Length of full decompressed text: {len(decompressed_full)}")

# Verifikasi
print(f"\nOriginal text matches decompressed text: {full_text == decompressed_full}")