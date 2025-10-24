class ZScore:
    def __init__(self):
        self.n = 0
        self.mean = 0.0
        self.M2 = 0.0

    def update(self, x: float):
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        delta2 = x - self.mean
        self.M2 += delta * delta2

    @property
    def variance(self):
        return self.M2 / (self.n - 1) if self.n > 1 else 0.0

    @property
    def std(self):
        return self.variance ** 0.5

    def z(self, x: float) -> float:
        s = self.std
        return (x - self.mean) / s if s > 1e-9 else 0.0