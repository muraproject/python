import qrcode

# Link langsung milikmu
url = "http://main.iotweb.my.id:3311/pc/smartlocker"

# Generate QR code
qr = qrcode.make(url)

# Simpan sebagai gambar
qr.save("qr_kulink.png")
