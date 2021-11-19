'''
exceptions.py: exceptions defined by Foliage

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code is
open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''


# Base class.
# .............................................................................
# The base class makes it possible to use a single test to distinguish between
# exceptions generated by Foliage and exceptions generated by something else.

class FoliageException(Exception):
    '''Base class for Foliage exceptions.'''
    pass


# Exception classes.
# .............................................................................

class FolioError(FoliageException):
    '''Unrecoverable problem involving interactions with the FOLIO server.'''
    pass
