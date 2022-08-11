from tuna.utils.History_new import History

h1 = History('x', 'y', 'string', 'z', title='Test', track_stats='auto')
h1.add_event(3, 5, 'A', 6)
h1.add_event(5, 2, 'B', 7)
h1.add_event(-1, 6, 'C', 2)
print(h1)
h1.print_overview(verbose=True)
h1.plot(filename='/home/saud/for_experimentation/__delete_this_temp_fig.png')

h2 = History('x', 'y', 'string', 'z', title='Test2', track_stats='auto')
h2.add_event(15, 18, 'C', 2)
h2.add_event(13, 12, 'B', 7)
h2.add_event(11, 28, '1', 8)

print(h2)
h2.print_overview()

h = h1 + h2
print(h)
h.print_overview(verbose=True)

print(h.to_list())

print(h.get_stat(stat_name='avg'))
print(h.get_stats())

print(len(h))
