##############################################################################
#
# Copyright (c) 2002 Zope Foundation and Contributors.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
""" Unit tests for DirectoryView module.
"""

import unittest
import Testing

import sys
from os import remove, mkdir, rmdir
from os.path import join
from tempfile import mktemp

from Products.CMFCore.tests import _globals
from Products.CMFCore.tests.base.dummy import DummyFolder
from Products.CMFCore.tests.base.testcase import FSDVTest
from Products.CMFCore.tests.base.testcase import WarningInterceptor
from Products.CMFCore.tests.base.testcase import WritableFSDVTest

from Products.CMFCore.DirectoryView import DirectoryView


class DummyDirectoryView(DirectoryView):
    def __of__(self, parent):
        return DummyDirectoryViewSurrogate()

class DummyDirectoryViewSurrogate:
    pass


class DirectoryViewPathTests(unittest.TestCase, WarningInterceptor):
    """
    These test that, no matter what is stored in their dirpath,
    FSDV's will do their best to find an appropriate skin
    and only do nothing in the case where an appropriate skin
    can't be found.
    """

    def setUp(self):
        from Products.CMFCore.DirectoryView import registerDirectory
        from Products.CMFCore.DirectoryView import addDirectoryViews
        registerDirectory('fake_skins', _globals)
        self.ob = DummyFolder()
        addDirectoryViews(self.ob, 'fake_skins', _globals)

    def tearDown(self):
        self._free_warning_output()

    def test__generateKey(self):
        from Products.CMFCore.DirectoryView import _generateKey

        key = _generateKey('Products.CMFCore', 'tests')
        self.assertEqual(key.split(':')[0], 'Products.CMFCore')

        subkey = _generateKey('Products.CMFCore', 'tests\foo')
        self.failUnless(subkey.startswith(key))

    def test__findProductForPath(self):
        from Products.CMFCore.DirectoryView import _findProductForPath

        cmfpath = sys.modules['Products.CMFCore'].__path__[0]
        self.assertEqual(_findProductForPath(cmfpath),
                         ('Products.CMFCore', ''))

        cmfpath = join(cmfpath, 'tests')
        self.assertEqual(_findProductForPath(cmfpath),
                ('Products.CMFCore', 'tests'))

    def test_getDirectoryInfo(self):
        skin = self.ob.fake_skin
        skin.manage_properties('Products.CMFCore.tests:fake_skins/fake_skin')
        self.failUnless( hasattr(self.ob.fake_skin, 'test1'),
                         self.ob.fake_skin.getDirPath() )

    # Test we do nothing if given a really wacky path
    def test_UnhandleableExpandPath( self ):
        self._trap_warning_output()
        file = mktemp()
        self.ob.fake_skin.manage_properties(file)
        self.assertEqual(self.ob.fake_skin.objectIds(),[])
        # Check that a warning was raised.
        from Products.CMFCore import DirectoryView
        warnings = [t[0] for t in DirectoryView.__warningregistry__]
        text = 'DirectoryView fake_skin refers to a non-existing path %r' % file
        self.assert_(text in warnings)
        self.failUnless(text in self._our_stderr_stream.getvalue())

    # this test tests that registerDirectory creates keys in the right format.
    def test_registerDirectoryKeys(self):
        from Products.CMFCore.DirectoryView import _dirreg
        dirs = _dirreg._directories
        self.failUnless( dirs.has_key('Products.CMFCore.tests:fake_skins/fake_skin'),
                         dirs.keys() )
        self.assertEqual( self.ob.fake_skin.getDirPath(),
                          'Products.CMFCore.tests:fake_skins/fake_skin' )


class DirectoryViewTests( FSDVTest ):

    def setUp( self ):
        FSDVTest.setUp(self)
        self._registerDirectory(self)

    def test_addDirectoryViews( self ):
        # Test addDirectoryViews
        # also test registration of directory views doesn't barf
        pass

    def test_DirectoryViewExists( self ):
        # Check DirectoryView added by addDirectoryViews
        # appears as a DirectoryViewSurrogate due
        # to Acquisition hackery.
        from Products.CMFCore.DirectoryView import DirectoryViewSurrogate
        self.failUnless(isinstance(self.ob.fake_skin,DirectoryViewSurrogate))

    def test_DirectoryViewMethod( self ):
        # Check if DirectoryView method works
        self.assertEqual(self.ob.fake_skin.test1(),'test1')

    def test_properties(self):
        # Make sure the directory view is reading properties
        self.assertEqual(self.ob.fake_skin.testPT.title, 'Zope Pope')

    def test_ignored(self):
        # Test that "artifact" files and dirs are ignored
        for name in '#test1', 'CVS', '.test1', 'test1~':
            assert name not in self.ob.fake_skin.objectIds(), \
                   '%s not ignored' % name

    def test_surrogate_writethrough(self):
        # CMF Collector 316: It is possible to cause ZODB writes because
        # setting attributes on the non-persistent surrogate writes them
        # into the persistent DirectoryView as well. This is bad in situations
        # where you only want to store markers and remove them before the
        # transaction has ended - they never got removed because there was
        # no equivalent __delattr__ on the surrogate that would clean up
        # the persistent DirectoryView as well.
        fs = self.ob.fake_skin
        test_foo = 'My Foovalue'
        fs.foo = test_foo

        self.assertEqual(fs.foo, test_foo)
        self.assertEqual(fs.__dict__['_real'].foo, test_foo)

        del fs.foo

        self.assertRaises(AttributeError, getattr, fs, 'foo')
        self.assertRaises( AttributeError
                         , getattr
                         , fs.__dict__['_real']
                         , 'foo'
                         )


class DirectoryViewIgnoreTests(FSDVTest):

    def setUp( self ):
        FSDVTest.setUp(self)
        self.manual_ign = ('CVS', 'SVN', 'test_manual_ignore.py')
        self._registerDirectory(self , ignore=self.manual_ign)

    def test_ignored(self):
        # Test that "artifact" files and dirs are ignored,
        # even when a custom ignore list is used; and that the
        # custom ignore list is also honored
        auto_ign = ('#test1', '.test1', 'test1~')
        must_ignore = self.manual_ign + auto_ign + ('test_manual_ignore',)
        visible = self.ob.fake_skin.objectIds()

        for name in must_ignore:
            self.failIf(name in visible)


class DirectoryViewFolderTests(FSDVTest):

    def setUp(self):
        FSDVTest.setUp(self)
        self._registerDirectory(self)

    def tearDown(self):
        from Products.CMFCore import DirectoryView
        # This is nasty, but there is no way to unregister anything
        # right now...
        metatype_registry = DirectoryView._dirreg._meta_types
        if 'FOLDER' in metatype_registry.keys():
            del metatype_registry['FOLDER']
        FSDVTest.tearDown(self)

    def test_DirectoryViewMetadata(self):
        # Test to determine if metadata shows up correctly on a
        # FSDV that has a corresponding .metadata file
        testfolder = self.ob.fake_skin.test_directory
        self.assertEqual(testfolder.title, 'test_directory Title')

    def test_DirectoryViewMetadataOnPropertyManager(self):
        # Test to determine if metadata shows up correctly on a
        # FSDV that has a corresponding .metadata file
        testfolder = self.ob.fake_skin.test_directory
        self.assertEqual(testfolder.getProperty('title'), 'test_directory Title')

    def test_DirectoryViewFolderDefault(self):
        # Test that a folder inside the fake skin really is of type
        # DirectoryViewSurrogate
        from Products.CMFCore.DirectoryView import DirectoryViewSurrogate
        testfolder = self.ob.fake_skin.test_directory
        self.failUnless(isinstance(testfolder, DirectoryViewSurrogate))

    def test_DirectoryViewFolderCustom(self):
        # Now we register a different class under the fake meta_type
        # "FOLDER" and test again...
        from Products.CMFCore.DirectoryView import registerMetaType
        registerMetaType('FOLDER', DummyDirectoryView)

        # In order to regenerate the FSDV data we need to remove and
        # register again, that way the newly registered meta_type is used
        self.ob._delObject('fake_skin')
        self._registerDirectory(self)
        testfolder = self.ob.fake_skin.test_directory
        self.failUnless(isinstance(testfolder, DummyDirectoryViewSurrogate))


class DebugModeTests(WritableFSDVTest):

    def setUp( self ):
        WritableFSDVTest.setUp(self)
        self.test1path = join(self.skin_path_name,'test1.py')
        self.test2path = join(self.skin_path_name,'test2.py')
        self.test3path = join(self.skin_path_name,'test3')

        # initialise skins
        self._registerDirectory(self)

        # add a method to the fake skin folder
        self._writeFile(self.test2path, "return 'test2'")

        # edit the test1 method
        self._writeFile(self.test1path, "return 'new test1'")

        # add a new folder
        mkdir(self.test3path)

    def test_AddNewMethod( self ):
        # See if a method added to the skin folder can be found
        self.assertEqual(self.ob.fake_skin.test2(),'test2')

    def test_EditMethod( self ):
        # See if an edited method exhibits its new behaviour
        self.assertEqual(self.ob.fake_skin.test1(),'new test1')

    def test_NewFolder( self ):
        # See if a new folder shows up
        from Products.CMFCore.DirectoryView import DirectoryViewSurrogate
        self.failUnless(isinstance(self.ob.fake_skin.test3,
                                   DirectoryViewSurrogate))
        self.ob.fake_skin.test3.objectIds()

    def test_DeleteMethod( self ):
        # Make sure a deleted method goes away
        remove(self.test2path)
        self.failIf(hasattr(self.ob.fake_skin,'test2'))

    def test_DeleteAddEditMethod( self ):
        # Check that if we delete a method, then add it back,
        # then edit it, the DirectoryView notices.
        # This exercises yet another Win32 mtime weirdity.
        remove(self.test2path)
        self.failIf(hasattr(self.ob.fake_skin,'test2'))

        # add method back to the fake skin folder
        self._writeFile(self.test2path, "return 'test2.2'")

        # check
        self.assertEqual(self.ob.fake_skin.test2(),'test2.2')

        # edit method
        self._writeFile(self.test2path, "return 'test2.3'")

        # check
        self.assertEqual(self.ob.fake_skin.test2(),'test2.3')

    def test_DeleteFolder( self ):
        # Make sure a deleted folder goes away
        rmdir(self.test3path)
        self.failIf(hasattr(self.ob.fake_skin,'test3'))


def test_suite():
    import Globals # for data
    tests = [unittest.makeSuite(DirectoryViewPathTests),
             unittest.makeSuite(DirectoryViewTests),
             unittest.makeSuite(DirectoryViewIgnoreTests),
             unittest.makeSuite(DirectoryViewFolderTests),
            ]
    if Globals.DevelopmentMode:
        tests.append(unittest.makeSuite(DebugModeTests))
    return unittest.TestSuite(tests)
