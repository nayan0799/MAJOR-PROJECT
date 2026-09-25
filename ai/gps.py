import random
try:
    import serial
except ImportError:
    serial=None

class GPS:
    def __init__(self,mode="mock",port="COM3",baud=9600):
        self.mode=mode
        self.ser=None
        if mode=="serial":
            if serial is None: raise RuntimeError("Install pyserial")
            self.ser=serial.Serial(port,baud,timeout=1)

    def read(self):
        if self.mode=="mock":
            return {"latitude":23.8315+random.uniform(-.0003,.0003),
                    "longitude":91.2868+random.uniform(-.0003,.0003)}
        for _ in range(20):
            line=self.ser.readline().decode("ascii","ignore").strip()
            if line.startswith(("$GPGGA","$GNGGA")):
                p=line.split(",")
                if len(p)>6 and p[2] and p[4]:
                    return self.convert(p[2],p[3],p[4],p[5])
            if line.startswith(("$GPRMC","$GNRMC")):
                p=line.split(",")
                if len(p)>6 and p[3] and p[5]:
                    return self.convert(p[3],p[4],p[5],p[6])
        return {"latitude":None,"longitude":None}

    @staticmethod
    def convert(lat,ld,lon,lod):
        a=float(lat[:2])+float(lat[2:])/60
        b=float(lon[:3])+float(lon[3:])/60
        return {"latitude":-a if ld=="S" else a,
                "longitude":-b if lod=="W" else b}
