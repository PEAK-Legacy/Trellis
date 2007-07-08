def additional_tests():
    import doctest
    return doctest.DocFileSuite(
        'README.txt', 'Tasks.txt',
        optionflags=doctest.ELLIPSIS|doctest.NORMALIZE_WHITESPACE,
    )

