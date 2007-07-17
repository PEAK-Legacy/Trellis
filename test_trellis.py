def additional_tests():
    import doctest
    return doctest.DocFileSuite(
        'README.txt', 'Internals.txt', 'Specification.txt',
        optionflags=doctest.ELLIPSIS|doctest.NORMALIZE_WHITESPACE,
    )

