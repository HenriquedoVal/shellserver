import zlib


def search_idx(idx_path: str, hash_: str, rt_offset=False) -> int:
    layer1_idx = int(hash_[:2], 16)
    found = False

    with open(idx_path, 'rb') as file:
        file.seek(8 + 4 * layer1_idx)
        files_before = int.from_bytes(file.read(4))
        file.seek(1028)
        total_files = int.from_bytes(file.read(4))

        file.seek(
            1032  # end of fanout_layer1
            + 20 * (files_before - 1)  # each will have 20 bytes
        )

        while not found:
            file_hash_bytes = file.read(20)
            file_hash = hex(int.from_bytes(file_hash_bytes))[2:].zfill(40)

            if hash_ == file_hash:
                found = True

            elif int(file_hash[:2], 16) > layer1_idx:
                break

            elif file.tell() >= 1032 + 20 * total_files:
                break

        if not rt_offset:
            return found

        if found:
            file.seek(
                1032
                + 20 * total_files  # jump layer2
                + 4 * total_files  # jump layer3
                + 4 * (files_before - 1)
            )
            return int.from_bytes(file.read(4))


def get_content_by_offset(pack_path: str, offset: int) -> bytes:
    with open(pack_path, 'rb') as file:
        file.seek(offset)

        int_ = int.from_bytes(file.read(1))
        binary = f'{int_:b}'.zfill(8)
        msb = binary.startswith('1')
        # size = binary[1:]

        while msb:
            int_ = int.from_bytes(file.read(1))
            binary = f'{int_:b}'.zfill(8)
            msb = binary.startswith('1')

        # easier than getting the size of file
        # but may be slower
        try:
            return zlib.decompress(file.read())
        except zlib.error:
            pass


#
# These are a study on packfiles
#


def __parse_idx(idx_path: str):
    with open(idx_path, 'rb') as file:
        content = file.read()

    constant = content[:4]
    print('constant:', *[constant[idx] for idx in range(4)])
    version = content[4:8]
    print(f'{version=}')

    fanout_layer1 = [content[i:i + 4] for i in range(8, 1032, 4)]
    print('len layer1:', len(fanout_layer1))
    print('entry 108 in fanout:', fanout_layer1[108])
    print('entry 109 in fanout:', fanout_layer1[109])

    total_files = int.from_bytes(fanout_layer1[-1], 'big')
    print(f'{total_files=}')

    # file names
    stop = total_files * 20 + 1032
    fanout_layer2 = [content[i:i + 20] for i in range(1032, stop, 20)]
    fanout_layer2 = [f'{int.from_bytes(i):x}'.zfill(40) for i in fanout_layer2]
    print('layer2:')
    for i, j in enumerate(fanout_layer2):
        print(i + 1, j)
    print('len layer2:', len(fanout_layer2))

    # redundancy check
    start = stop
    stop = total_files * 4 + start
    fanout_layer3 = [content[i:i + 4] for i in range(start, stop, 4)]
    print('len layer3:', len(fanout_layer3))
    print('len layer3[0]:', len(fanout_layer3[0]))
    print('layer3:', fanout_layer3)

    # packfile offsets for each object
    start = stop
    stop = total_files * 4 + start
    fanout_layer4 = [content[i:i + 4] for i in range(start, stop, 4)]
    print('len layer4:', len(fanout_layer4))
    print('len layer4[0]:', len(fanout_layer4[0]))
    print('layer4:', fanout_layer4)

    # offset for objects > 2GB
    # it will be signed with msb
    # it's easier to check if there is data between next stop and
    # len(content) - 40
    start = stop
    stop = len(content) - 40
    layer5 = content[start:stop]

    if layer5:
        fanout_layer5 = [content[i:i + 8] for i in range(start, stop, 8)]
        print('len layer5:', len(fanout_layer5))
        print('len layer5[0]:', len(fanout_layer5[0]))
        print('layer5:', fanout_layer5)

    start = stop
    packfile_checksum = content[start:start + 20]
    index_checksum = content[start + 20:start + 40]
    print(f'{packfile_checksum=}')
    print(f'{len(packfile_checksum)=}')
    print(f'{index_checksum=}')
    print(f'{len(index_checksum)=}')

    print('End?', len(content[start + 40:]) == 0)


def __parse_pack(pack_path: str):
    # there is no way of getting all files from it it isnt passed
    # the offset of the file
    # As is, it will only return the first file in pack

    with open(pack_path, 'rb') as file:
        content = file.read()

    pack = content[:4] == b'PACK'
    version = content[4:8]
    objs_in_pack = int.from_bytes(content[8:12], 'big')
    print(f'{pack=}, {version=}, {objs_in_pack=}')

    start = 12
    size = ''

    binary = f'{content[start]:b}'.zfill(8)
    msb = binary.startswith('1')
    type_ = binary[1:4]
    size += str(int(binary[4:], 2))
    print(f'{binary=}, {msb=}, {type_=}')

    while msb:
        start += 1
        binary = f'{content[start]:b}'.zfill(8)
        msb = binary.startswith('1')
        size += ' ' + str(int(binary[1:], 2))
        print(f'{binary=}, {msb=}')

    start += 1
    print('start:', start)
    # this size calculation is wrong!!!
    print('size before convertion:', size)
    size = int(size[::-1].replace(' ', '', -1), 16)
    print(f'{size=}')

    # just decompress from offset to end and zlib will handle it
    inflated = zlib.decompress(content[start:])
    # it will return the content of the first file
    print(inflated, 'len:', len(inflated))

    checksum = content[-20:]
    checksum = f'{int.from_bytes(checksum, "big"):x}'
    print(f'{checksum=}, {len(checksum)=}')
