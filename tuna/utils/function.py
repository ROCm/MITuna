import math
import numpy as np
from enum import Enum
from collections import OrderedDict
from collections.abc import Iterator

from tuna.utils import logging
from tuna.utils.helpers import pretty_iterator


class WARNING_CODES(Enum):
    SORT_ORDER_VIOLATED = 0

class Function(Iterator):
    NAMES_OF_STATS = ['sum', 'sumsq'] +\
                     ['max', 'min', 'argmax', 'argmin'] +\
                     ['avg', 'std']

    def __init__(self, name, track_stats = 'auto'):
        self.name = name
        self.track_stats = track_stats

        self.f = OrderedDict()
        self.sorted_along = None
        self.sort_order = None

        self.define = self.__init_define__

    def to_str(self, max_length=None):
        s = pretty_iterator( self, sep=', ', max_items=max_length )
        return f"{self.name} = {{ {s} }}"

    def to_pairs(self):
        return self.f.items()

    def get_x(self):
        return self.f.keys()

    def get_y(self):
        return self.f.values()

    def to_list_of_pairs(self, sorted_along=None, nondecreasing=True):
        if sorted_along is not None:
            if sorted_along == 'x':
                coord = 0
            elif sorted_along == 'y':
                coord = 1
            else:
                raise ValueError("`sorted_along` can either be 'x' or 'y' or `None`")

            return sorted( self, key=lambda pair: pair[coord] , reverse=not nondecreasing )

        else:
            return list( self )


    def to_array_of_pairs(self, sorted_along=None, nondecreasing=True):
        if sorted_along is not None:
            return np.array( self.to_list_of_pairs(sorted_along=sorted_along, nondecreasing=nondecreasing) )
        else:
            return np.array( self )

    def to_sorted(self, along='x', nondecreasing=True, set_name=None, set_track_stats=None):
        if along not in ['x', 'y']:
            raise ValueError("`along` can either be 'x' or 'y'")

        if set_name is None:
            set_name = self.name
        if set_track_stats is None:
            set_track_stats = self.track_stats

        sorted_pairs = self.to_list_of_pairs(sorted_along=along, nondecreasing=nondecreasing)
        f = Function(set_name, track_stats=set_track_stats)
        for x, y in sorted_pairs:
            f.define(x, y)
        f.sorted_along = along
        f.sort_order = 'nondecreasing' if nondecreasing else 'nonincreasing'
        return f

    @property
    def domain(self):
        return set( self.f.keys() )

    @property
    def image(self):
        return set( self.f.values() )

    @property
    def xvals(self):
        return self.f.keys()

    @property
    def yvals(self):
        return self.f.values()

    def is_domain_equal(self, other) -> bool:
        return self.domain == other.domain

    def is_image_equal(self, other):
        return self.image == other.image


    def plot(self, ax, title=None, xlabel=None, ylabel=None):
        sorted_pairs = self.to_array_of_pairs( sorted_along='x', nondecreasing=True )
        xvals, yvals = sorted_pairs.T
        ax.plot( xvals, yvals, 'tab:red' )

        if self.track_stats is True:
            #ax.axhline( y=self.min, color='red', linestyle='-', alpha=0.1)
            ax.axhline( y=self.avg, color='red', linestyle=':', alpha=0.3)
            #ax.axhline( y=self.max, color='red', linestyle='-', alpha=0.1)

        if title is not None:
            ax.set_title( title )
        if xlabel is not None:
            ax.set_xlabel( xlabel )
        if ylabel is not None:
            ax.set_ylabel( ylabel )

    def __len__(self):
        return len(self.f)

    def __iter__(self):
        return iter( self.f.items() )

    def __next__(self):
        return next( self.f.items() )

    def __call__(self, x):
        try:
            return self.f[x]
        except KeyError as err:
            message = f"{self.name}({x}) has not been defined"
            err.args = (message,) + err.args[1:]
            raise 

    def __getitem__(self, x):
        return self.__call__(x)

    def __eq__(self, other):
        if not self.is_domain_equal(other):
            raise KeyError( f"domain mismatch: the functions {self.name} and {other.name} must have the same domain" )

        return self.f == other.f

    def __gt__(self, other):
        try:
            for x, y in self:
                if y <= other(x):
                    return False
            return True
        except KeyError as err:
            message = f"domain mismatch: the functions {self.name} and {other.name} must have the same domain"
            err.args = (message,) + err.args[1:]
            raise 

    def __ge__(self, other):
        try:
            for x, y in self:
                if y < other(x):
                    return False
            return True
        except KeyError as err:
            message = f"domain mismatch: the functions {self.name} and {other.name} must have the same domain"
            err.args = (message,) + err.args[1:]
            raise 

    def __lt__(self, other):
        try:
            for x, y in self:
                if y >= other(x):
                    return False
            return True
        except KeyError as err:
            message = f"domain mismatch: the functions {self.name} and {other.name} must have the same domain"
            err.args = (message,) + err.args[1:]
            raise 

    def __le__(self, other):
        try:
            for x, y in self:
                if y > other(x):
                    return False
            return True
        except KeyError as err:
            message = f"domain mismatch: the functions {self.name} and {other.name} must have the same domain"
            err.args = (message,) + err.args[1:]
            raise 

    def __repr__(self):
        return self.to_str(max_length=10)

    def __getattr__(self, name):
        if name in Function.NAMES_OF_STATS: 
            if not self.track_stats:
                raise Exception(f"{name} unknown: {self.name} has stats tracking disabled")
            else:
                raise Exception(f"{self.name} has to be defined at atleast one point for {name} to be defined")
        else:
            return super().__getattribute__(name)

    # ----------------------------------------------------
    # STRICTLY IMPLEMENTATION SPECIFIC DETAILS FOLLOW
    #       DONOT CALL ANY OF THIS FROM YOUR CODE! YOU MAY
    #       END UP VIOLATING INVARIANTS
    # ----------------------------------------------------

    def __promise_to_update_lasts__(self, x, y):
        """ returns a promise to update xlast to x, and ylast to y. """
        # TODO update this to use yield and be a context manager
        def __update_lasts__():
            self.__xlast__ = x
            self.__ylast__ = y 
        return __update_lasts__

    def __init_define__(self, x, y):
        self.f[x] = y
        self.__take_up_on_the_promise_to_update_lasts__ = self.__promise_to_update_lasts__(x, y)

        self.define = self.__define__

        if self.__are_stats_trackable__(x, y):
            if self.track_stats == 'auto':
                self.track_stats = True
        else:
            if self.track_stats == 'auto':
                self.track_stats = False
            elif self.track_stats is True:
                logging.error(f"can't compute stats for {self.name}: required operations don't appear" + \
                              f" to be supported by this type.\nexecution might error out")

        if self.track_stats:
            self.__init_stats__(x, y)

        self.__consistency_checks__(x, y)

    def __define__(self, x, y, redefine=False):
        if x in self.domain and not redefine:
            raise ValueError(f"Can't define {self.name}({x})={y}: {self.name}({x}) is already defined to be {self(x)}.\n" + \
                    "Set redefine to True to redefine {se.fname}({x}) to {y}.")

        self.__take_up_on_the_promise_to_update_lasts__()
        self.f[x] = y
        self.__take_up_on_the_promise_to_update_lasts__ = self.__promise_to_update_lasts__(x, y)

        if self.track_stats:
            self.__update_stats__(x, y)

        self.__consistency_checks__(x, y)

    def __are_stats_trackable__(self, x, y):
        try:
            # simulate the operations that take place when sum/sumsq are computed 
            fake_sum = y + y
            fake_sumsq = y**2 + y**2

            # simulate the comparisions that take place when max/min are computed 
            y > y
            y < y

            # simulate the operations that take place when avg/std are computed 
            fake_avg = 0.5 * y + 0.5 * y
            fake_std = math.sqrt( 2 * fake_sumsq - fake_sum**2 ) / 2

            # if all the simulations go through, the stats are trackable
            return True

        except Exception as e:
            return False

    def __init_stats__(self, x, y):
        n = 1

        # init sum, sumsq (used to update std)
        self.sum = y
        self.sumsq = y**2

        # init max, argmax, min, argmin
        self.max = y
        self.argmax = x
        self.min = y
        self.argmin = x

        # init avg, std
        self.avg = y
        self.std = 0

    def __update_stats__(self, x, y):
        n = len(self)

        # update sum, sumsq (used to update std)
        self.sum += y
        self.sumsq += y**2

        # update max, argmax, min, argmin
        if y > self.max:
            self.max = y
            self.argmax = x
        if y < self.min:
            self.min = y
            self.argmin = x

        # update avg, std
        self.avg = (n-1)/n * self.avg + 1/n * y

        # TODO
        # Donald Knuth's The Art of Computer Programming, Volume 2, Section 4.2.2 has a better
        # way of computing stds, which doesn't run into the complex numbers problem, and
        # is also more accurate
        tau = n * self.sumsq - self.sum**2 
        if tau < 0:
            if not isinstance(self.std, complex):
                logging.warning( 'the std of the function {self.name} has become complex' )
            self.std = complex(0, math.sqrt(-tau) / n) 
        else:
            if isinstance(self.std, complex):
                logging.warning( 'the std of the function {self.name} is back real again' )
            self.std = math.sqrt(tau) / n

                
    def __consistency_checks__(self, x, y):
        # strict checks
        ...

        # warnings
        warnings_triggered = []
    
        if self.sorted_along == 'x' and len(self) > 1:
            if (self.sort_order == 'nondecreasing' and self.x < self.__lastx__) or \
               (self.sort_order == 'nonincreasing' and self.x > self.__lastx__):
                self.sorted_along = None
                self.sort_order = None
                logging.warning("{self.name} is not longer sorted along x")
                warnings_triggered.append( WARNING_CODES['SORT_ORDER_VIOLATED'] )

        if self.sorted_along == 'y' and len(self) > 1:
            if (self.sort_order == 'nondecreasing' and self.y < self.__lasty__) or \
               (self.sort_order == 'nonincreasing' and self.y > self.__lasty__):
                self.sorted_along = None
                self.sort_order = None
                logging.warning('{self.name} is no longer sorted along y')
                warnings_triggered.append( WARNING_CODES['SORT_ORDER_VIOLATED'] )

        return warnings_triggered
