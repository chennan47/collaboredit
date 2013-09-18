from zlib import compress
  
def distance (sx, sy):
    ab =len (compress (sx + sy))
    a ,b =len (compress(sx)),len (compress(sy))
    return 1.0 -(0.0 + a + b - ab )/max (a ,b)

def main():
    while True:
        sx = raw_input("enter string sx: ").strip()
        sy = raw_input("enter string sy: ").strip()
        print("Compression distance: %.2f" % distance(sx, sy))

if __name__ == "__main__":
    main()