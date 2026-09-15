"""Prove platter sum helper expectation used by sale.order validation."""
def platter_total(chicken=0, gyro=0, falafel=0, steak=0, salmon=0, lamb=0):
    return chicken + gyro + falafel + steak + salmon + lamb

assert platter_total(15, 10) == 25
assert platter_total(15, 9) != 25
assert platter_total(15, 10, steak=1) != 25
print("PASS platter balance helpers")
