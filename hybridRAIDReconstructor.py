import sys
import os
import struct
import argparse

class HybridRAID:
    def __init__(self, InputDirectory, OutputDirectory):
        self.InputPath = InputDirectory
        self.OutputPath = OutputDirectory
        
        self.filePathList = []
        fileList = os.listdir(self.InputPath)
        fileList.sort()
        for filename in fileList:
            filePath = self.InputPath + '\\' + filename
            self.filePathList.append(filePath)

        self.partitionList = []
        self.bvdList = []

    def __del__(self):
        self.fp.close()

    def _ParseMBR(self):
        for file in self.filePathList:
            try:
                self.fp = open(file, 'rb')
                block = self.fp.read(512)
            except IOError:
                print('Error : Could not image file open')

            if block[510:] == b'\x55\xAA':
                type = block[450]
                startOffset = struct.unpack('<i', block[454:458])[0]
                size = struct.unpack('<i', block[458:462])[0]
                if startOffset > 0 and size > 0:
                    self.partitionList.append([file, startOffset*512, size*512])

                type = block[466]
                startOffset = struct.unpack('<i', block[470:474])[0]
                size = struct.unpack('<i', block[474:478])[0]
                if startOffset > 0 and size > 0:
                    self.partitionList.append([file, startOffset*512, size*512])

                type = block[482]
                startOffset = struct.unpack('<i', block[486:490])[0]                
                size = struct.unpack('<i', block[490:494])[0]                
                if startOffset > 0 and size > 0 and type is 15:
                    extendOffset = startOffset

                    while True:
                        self.fp.seek(extendOffset*512)
                        extendBlock = self.fp.read(512)

                        type = extendBlock[450]
                        startOffset = struct.unpack('<i', extendBlock[454:458])[0]
                        size = struct.unpack('<i', extendBlock[458:462])[0]
                        if startOffset > 0 and size > 0:
                            self.partitionList.append([file, (extendOffset+startOffset)*512, size*512])

                        type = extendBlock[466]
                        startOffset = struct.unpack('<i', extendBlock[470:474])[0]
                        size = struct.unpack('<i', extendBlock[474:478])[0]
                        if startOffset > 0 and size > 0 and (type is 5 or type is 15):
                            extendOffset = extendOffset + startOffset
                            continue
                        else:
                            break
                elif startOffset > 0 and size > 0 and type is not 15:
                    self.partitionList.append([file, startOffset*512, size*512])

                type = block[498]
                startOffset = struct.unpack('<i', block[502:506])[0]                
                size = struct.unpack('<i', block[506:510])[0]                
                if startOffset > 0 and size > 0 and type is 15:
                    extendOffset = startOffset

                    while True:
                        self.fp.seek(extendOffset*512)
                        extendBlock = self.fp.read(512)

                        type = extendBlock[450]
                        startOffset = struct.unpack('<i', extendBlock[454:458])[0]
                        size = struct.unpack('<i', extendBlock[458:462])[0]
                        if startOffset > 0 and size > 0:
                            self.partitionList.append([file, (extendOffset+startOffset)*512, size*512])

                        type = extendBlock[466]
                        startOffset = struct.unpack('<i', extendBlock[470:474])[0]
                        size = struct.unpack('<i', extendBlock[474:478])[0]
                        if startOffset > 0 and size > 0 and type is 15:
                            extendOffset = extendOffset + startOffset
                            continue
                        else:
                            break
                elif startOffset > 0 and size > 0 and type is not 15:
                    self.partitionList.append([file, startOffset*512, size*512])
            else:
                self.partitionList.append([file, 0, os.path.getsize(file)])
            self.fp.close()
        
        if len(self.partitionList) > 0:
            return True
        else:
            return False

    def _CreateBVD(self):
        for partition in self.partitionList:
            try:
                self.fp = open(partition[0], 'rb')
                self.fp.seek(partition[1]+0x1000)
                block = self.fp.read(512)
            except IOError:
                print('Error : Could not image file open')
                exit(1)

            self.fp.close()

            signature = block[0:4]
            if signature == b'\xFC\x4E\x2B\xA9':
                UUID = block[16:32]
                RAIDType = struct.unpack('<I', block[72:76])[0]
                stripeMap = struct.unpack('<I', block[76:80])[0]
                stripeSize = struct.unpack('<I', block[88:92])[0]
                numberOfDisks = struct.unpack('<I', block[92:96])[0]
                startOffset = struct.unpack('<Q', block[128:136])[0]
                sizeOfExtents = struct.unpack('<Q', block[136:144])[0]
                diskOrder = struct.unpack('<I', block[160:164])[0]
            else:
                continue

            check = False
            
            for atom in self.bvdList:
                if atom[0] == UUID:
                    # UUID, RAIDType, StripeSize, StripeMap, numberOfDiks, hasLVM, ExtentList, LVMList
                    # Extent List : filePath, Partition Start offset, Partition Size, ExtentStartOffset, Extent Size, diskOrder                                       
                    atom[5].append([partition[0], partition[1], partition[2], partition[1]+startOffset*512, sizeOfExtents*512, diskOrder])
                    check = True
                    break

            if check is False:
                ExtentList = []
                ExtentList.append([partition[0], partition[1], partition[2], partition[1]+startOffset*512, sizeOfExtents*512, diskOrder])
                self.bvdList.append([UUID, RAIDType, stripeMap, numberOfDisks, False, ExtentList, []])

        # print BVD info
        index = 1
        for atom in self.bvdList:
            print("RAID Group ", index)
            index = index + 1
            print(" - UUID :", atom[0])
            print(" - RAID Type : RAID Level", atom[1])
            if atom[1] is 5 or atom[1] is 6:
                if atom[2] is 0:
                    print(" - Stripe Map : left asymmetric")
                elif atom[2] is 1:
                    print(" - Stripe Map : right asymmetric")
                elif atom[2] is 2:
                    print(" - Stripe Map : left symmetric")
                elif atom[2] is 3:
                    print(" - Stripe Map : right symmetric")
            print(" - Number Of Disks :", atom[3])
            print(" - Extent List :")
            for extent in atom[5]:
                print("     image path :", extent[0], ", partition start offset :", extent[1], ", partition size :", extent[2], ", extent start Offset :", extent[3], ", extent size :", extent[4], ", diskOrder :", extent[5])
            print("\n")


    def _CreateVD(self):
        # Parsing the LVM
        Todo = 10

    def run(self):       
        if len(self.filePathList) <= 0:
            print('Error : Unable to read file in directory')
            exit()
        else:
            if self._ParseMBR() is False:
                print('Error : Unable to read file in directory')
                exit()
            else:
                if self._CreateBVD() is False:
                    print('Error : Linux RAID Superblock is not found')
                    exit()
                else:
                    self._CreateVD()
            


def main(DirectoryPath):
    parser = argparse.ArgumentParser(usage='HybridRAIDReconstructor --i INPUT_DIRECTORY --o OUTPUT_DIRECTORY', description='This tool is a tool to rebuild RAID against Linux based hybrid RAID')

    parser.add_argument('--i', required=False, metavar='InputDirectory', help='Enter directory where raw image exists')
    parser.add_argument('--o', required=True, metavar='OutputDirectory', help='Enter directory to save raw image')

    args = parser.parse_args()

    if os.path.isdir(args.i) is True and os.path.isdir(args.o) is True:
        hybrid = HybridRAID(args.i, args.o)
        hybrid.run()
    else:
        print('Error : Directory path is not exist')

if __name__ == "__main__":
    main(sys.argv)