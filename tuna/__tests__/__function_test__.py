from tuna.utils.function import Function
import matplotlib.pyplot as plt
import numpy
import pdb

f = Function(name='f', track_stats=True)
f.define(4, 5)
f.define(2, 90)
f.define(0, 33)
f.define(9, 18)
f.define(-1, -13)
f.define(-2, 19)

g = Function(name='g', track_stats=False)
g.define(9, 16)
g.define(4, 3)
g.define(-2, 15)
g.define(2, 16)
g.define(0, 30)
g.define(-1, -16)

print(f)
print(g)
print('relations')
print('f>g', f > g)
print('f>=g', f >= g)
print('f<g', f < g)
print('f<=g', f <= g)

if f.track_stats:
  assert f.max == numpy.max(list(f.f.values()))
  assert f.min == numpy.min(list(f.f.values()))
  assert f.argmax == list(f.f.keys())[numpy.argmax(list(f.f.values()))]
  assert f.argmin == list(f.f.keys())[numpy.argmin(list(f.f.values()))]
  assert f.sum == numpy.sum(list(f.f.values()))
  assert f.sumsq == numpy.sum([y**2 for y in list(f.f.values())])
  assert numpy.isclose(f.avg, numpy.mean(list(f.f.values())))
  assert numpy.isclose(f.std, numpy.std(list(f.f.values())))

print(f.to_str(max_items=3))

gdash = g.to_sorted()
print(list(gdash))

h = gdash.to_sorted(along='y',
                    nondecreasing=False,
                    set_name='h',
                    set_track_stats=True)
print(h)

if h.track_stats:
  assert h.max == numpy.max(list(h.f.values()))
  assert h.min == numpy.min(list(h.f.values()))
  assert h.argmax == list(h.f.keys())[numpy.argmax(list(h.f.values()))]
  assert h.argmin == list(h.f.keys())[numpy.argmin(list(h.f.values()))]
  assert h.sum == numpy.sum(list(h.f.values()))
  assert h.sumsq == numpy.sum([y**2 for y in list(h.f.values())])
  assert numpy.isclose(h.avg, numpy.mean(list(h.f.values())))
  assert numpy.isclose(h.std, numpy.std(list(h.f.values())))

print(h.domain)
print(h.image)
print(h.xvals)
print(h.yvals)

print(h.domain == gdash.domain)
print(h.image == gdash.image)
print(h.domain == Function('temp').domain)
print(h.image == f.image)

ax = plt.subplot()
h.plot(ax, title='Sample', xlabel='X Values', ylabel='Y Values')
plt.savefig('/home/saud/for_experimentation/__delete_this_fig.png')
