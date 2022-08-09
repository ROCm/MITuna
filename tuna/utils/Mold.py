import re

class Mold():
  """Mold to cast strings of one pattern to another.
  disclaimer: there are no *intentional* consistency checks. for example,
        if m = Mold('', 'A_B_C', '_', '_', 'NaN')
        then s = 'MeBeingDumb' isn't consistent with the
        from_ptrn string; the from_ptrn is an empty string!
        Ideally, m.cast(s) should throw an exception, but here,
        doing m.cast(s) will return 'NaN_NaN_NaN'. This
        behaviour might be useful in certain applications,
        though, because you may interpret a from_ptrn of '' to mean
        any string with no from_sep.
  """

  def __init__(self, from_ptrn, to_ptrn, from_sep, to_sep, filler=None):
    self.from_ptrn = from_ptrn
    self.to_ptrn = to_ptrn
    self.from_sep = str(from_sep)
    self.to_sep = str(to_sep)
    self.filler = str(filler)

    if self.from_sep == '':
      self.from_tokens = [self.from_ptrn]
    else:
      self.from_tokens = self.from_ptrn.split(self.from_sep)

    if self.to_sep == '':
      self.to_tokens = [self.to_ptrn]
    else:
      self.to_tokens = self.to_ptrn.split(self.to_sep)

    self.token_inds = [] # token_inds[i] tells where to find the ith token of
              # to_ptrn in from_ptrn

    for token2 in self.to_tokens:
      try:
        self.token_inds.append( self.from_tokens.index(token2) )
      except ValueError:
        self.token_inds.append( None )

  def cast(self, from_str):
    if self.from_sep == '':
      tokens = [from_str]
    else:
      tokens = from_str.split(self.from_sep)

    casted_tokens = []
    for ind in self.token_inds:
      if ind is None:
        casted_tokens.append(self.filler)
      else:
        casted_tokens.append(tokens[ind])

    return self.to_sep.join(casted_tokens)

  def __call__(self, string):
    return self.cast(string)

  def __str__(self):
    return '"%s" -> "%s"' % (self.from_ptrn, self.to_ptrn)

## general example
#m = Mold('U_A_B_C_A_D_E', 'U-A-F-A-C-E-P-P', '_', '-', 'NaN')
#print(m)
#print(m.cast("+1_1_2_3_1_4_5"))

## an example case where the absence of consistency checks can mess things up
# m = Mold('ada', 'A_B_C', '', '_', 'NaN')
# print(m)
# print(m.cast('MeBeingDumb'))
