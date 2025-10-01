import os
import time

from genmedia import imagen_t2i


def main():
    print(f"started at {time.strftime('%X')}")

    response = imagen_t2i(
        "新橋で酔い潰れているイルカ",
        os.getenv("GENMEDIA_BUCKET"),
    )
    print(response)
    print(f"finished at {time.strftime('%X')}")


if __name__ == "__main__":
    main()
