from test_sets import *
    
def additional_tests():
    import doctest, sys
    files = [
        'README.txt', 'Internals.txt', 'Specification.txt'
    ][sys.version<'2.4':]   # README.txt uses decorator syntax
    return doctest.DocFileSuite(
        optionflags=doctest.ELLIPSIS|doctest.NORMALIZE_WHITESPACE, *files        
    )

