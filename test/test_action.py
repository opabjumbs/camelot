import datetime
import logging
import os

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

from sqlalchemy import orm

import six

from camelot.admin.action import Action, GuiContext, ActionStep
from camelot.admin.action import ( list_action, application_action,
                                   document_action, form_action )
from camelot.core.exception import CancelRequest
from camelot.core.utils import pyqt, ugettext_lazy as _
from camelot.core.orm import Session
from camelot.model import party
from camelot.test import ModelThreadTestCase
from camelot.test.action import MockModelContext
from camelot.view import action_steps
from camelot.view.controls import tableview

from . import test_view
from . import test_proxy
from . import test_model

test_images = [os.path.join( os.path.dirname(__file__), '..', 'camelot_example', 'media', 'covers', 'circus.png') ]

class ActionBaseCase( ModelThreadTestCase ):

    def setUp(self):
        ModelThreadTestCase.setUp(self)
        self.gui_context = GuiContext()

    def test_action_step( self ):
        step = ActionStep()
        step.gui_run( self.gui_context )

    def test_action( self ):

        class CustomAction( Action ):
            shortcut = QtGui.QKeySequence.New

        action = CustomAction()
        action.gui_run( self.gui_context )
        self.assertTrue( action.get_name() )
        self.assertTrue( action.get_shortcut() )

class ActionWidgetsCase( ModelThreadTestCase ):
    """Test widgets related to actions.
    """

    images_path = test_view.static_images_path

    def setUp(self):
        from camelot.admin.action import ApplicationActionGuiContext, State
        from camelot.admin.application_admin import ApplicationAdmin
        from camelot_example.importer import ImportCovers
        ModelThreadTestCase.setUp(self)
        self.app_admin = ApplicationAdmin()
        self.action = ImportCovers()
        self.application_gui_context = ApplicationActionGuiContext()
        self.parent = QtGui.QWidget()
        enabled = State()
        disabled = State()
        disabled.enabled = False
        notification = State()
        notification.notification = True
        self.states = [ ( 'enabled', enabled),
                        ( 'disabled', disabled),
                        ( 'notification', notification) ]

    def grab_widget_states( self, widget, suffix ):
        for state_name, state in self.states:
            widget.set_state( state )
            self.grab_widget( widget, suffix='%s_%s'%( suffix,
                                                       state_name ) )

    def test_action_label( self ):
        from camelot.view.controls.action_widget import ActionLabel
        widget = ActionLabel( self.action,
                              self.application_gui_context,
                              self.parent )
        self.grab_widget_states( widget, 'application' )

    def test_action_push_botton( self ):
        from camelot.view.controls.action_widget import ActionPushButton
        widget = ActionPushButton( self.action,
                                   self.application_gui_context,
                                   self.parent )
        self.grab_widget_states( widget, 'application' )

    def test_hide_progress_dialog( self ):
        from camelot.view.action_runner import hide_progress_dialog
        dialog = QtGui.QWidget()
        dialog.show()
        self.application_gui_context.progress_dialog = dialog
        with hide_progress_dialog( self.application_gui_context ):
            self.assertTrue( dialog.isHidden() )
        self.assertFalse( dialog.isHidden() )

class ActionStepsCase( ModelThreadTestCase ):
    """Test the various steps that can be executed during an
    action.
    """

    images_path = test_view.static_images_path

    def setUp(self):
        ModelThreadTestCase.setUp(self)
        from camelot_example.model import Movie
        from camelot.admin.application_admin import ApplicationAdmin
        self.app_admin = ApplicationAdmin()
        self.context = MockModelContext()
        self.context.obj = Movie.query.first()
        self.gui_context = GuiContext()

# begin test application action
    def test_example_application_action( self ):
        from camelot_example.importer import ImportCovers
        from camelot_example.model import Movie
        # count the number of movies before the import
        movies = Movie.query.count()
        # create an import action
        action = ImportCovers()
        generator = action.model_run( None )
        select_file = six.advance_iterator( generator )
        self.assertFalse( select_file.single )
        # pretend the user selected a file
        generator.send(test_images)
        # continue the action till the end
        list( generator )
        # a movie should be inserted
        self.assertEqual( movies + 1, Movie.query.count() )
# end test application action

    def test_change_object( self ):
        from camelot.bin.meta import NewProjectOptions
        from camelot.view.action_steps.change_object import ChangeObject
        admin = self.app_admin.get_related_admin(NewProjectOptions)
        options = NewProjectOptions()
        options.name = 'Videostore'
        options.module = 'videostore'
        options.domain = 'example.com'
        change_object = ChangeObject(options, admin)
        dialog = change_object.render(self.gui_context)
        self.grab_widget( dialog )

    def test_select_file( self ):
        from camelot.view.action_steps import SelectFile
        select_file = SelectFile( 'Image Files (*.png *.jpg);;All Files (*)' )

    def test_select_item( self ):
        from camelot.view.action_steps import SelectItem

        # begin select item
        class SendDocumentAction( Action ):

            def model_run( self, model_context ):
                methods = [ ('email', 'By E-mail'),
                            ('fax',   'By Fax'),
                            ('post',  'By postal mail') ]
                method = yield SelectItem( methods, value='email' )
                # handle sending of the document

        # end select item

        action = SendDocumentAction()
        for step in action.model_run( self.context ):
            dialog = step.render()
            self.grab_widget( dialog )

    def test_text_document( self ):
        # begin text document
        class EditDocumentAction( Action ):

            def model_run( self, model_context ):
                document = QtGui.QTextDocument()
                document.setHtml( '<h3>Hello World</h3>')
                yield action_steps.EditTextDocument( document )
        # end text document

        action = EditDocumentAction()
        for step in action.model_run( self.context ):
            dialog = step.render()
            self.grab_widget( dialog )

    def test_print_chart( self ):

        # begin chart print
        class ChartPrint( Action ):

            def model_run( self, model_context ):
                from camelot.container.chartcontainer import BarContainer
                from camelot.view.action_steps import PrintChart
                chart = BarContainer( [1, 2, 3, 4],
                                      [5, 1, 7, 2] )
                print_chart_step = PrintChart( chart )
                print_chart_step.page_orientation = QtGui.QPrinter.Landscape
                yield print_chart_step
        # end chart print

        action = ChartPrint()
        steps = list( action.model_run( self.context ) )
        dialog = steps[0].render( self.gui_context )
        dialog.show()
        self.grab_widget( dialog )

    def test_print_preview( self ):
        from camelot.admin.action import GuiContext

        # begin webkit print
        class WebkitPrint( Action ):

            def model_run( self, model_context ):
                from PyQt4.QtWebKit import QWebView
                from camelot.view.action_steps import PrintPreview

                movie = model_context.get_object()

                document = QWebView()
                document.setHtml( '<h2>%s</h2>' % movie.title )

                yield PrintPreview( document )
        # end webkit print

        action = WebkitPrint()
        step = list( action.model_run( self.context ) )[0]
        dialog = step.render( GuiContext() )
        dialog.show()
        self.grab_widget( dialog )
        step.get_pdf()

    def test_print_html( self ):

        # begin html print
        class MovieSummary( Action ):

            verbose_name = _('Summary')

            def model_run(self, model_context):
                from camelot.view.action_steps import PrintHtml
                movie = model_context.get_object()
                yield PrintHtml( "<h1>This will become the movie report of %s!</h1>" % movie.title )
        # end html print

        action = MovieSummary()
        steps = list( action.model_run( self.context ) )
        dialog = steps[0].render( self.gui_context )
        dialog.show()
        self.grab_widget( dialog )

    def test_edit_profile(self):
        from camelot.view.action_steps.profile import EditProfiles
        step = EditProfiles([], '')
        dialog = step.render(self.gui_context)
        dialog.show()
        self.grab_widget(dialog)

    def test_open_file( self ):
        stream = six.BytesIO(b'1, 2, 3, 4')
        open_stream = action_steps.OpenStream( stream, suffix='.csv' )
        self.assertTrue( six.text_type( open_stream ) )
        action_steps.OpenString( six.b('1, 2, 3, 4') )
        context = { 'columns':['width', 'height'],
                    'table':[[1,2],[3,4]] }
        action_steps.OpenJinjaTemplate( 'list.html', context )
        action_steps.WordJinjaTemplate( 'list.html', context )

    def test_orm( self ):
        # prepare the model context
        contact = party.ContactMechanism( mechanism = ('email', 'info@test.be') )
        person = party.Person( first_name = u'Living',
                               last_name = u'Stone',
                               social_security_number = u'2003030212345' )
        party.PartyContactMechanism( party = person,
                                     contact_mechanism = contact )
        self.context.obj = person
        self.context.session.flush()

        # begin manual update

        class UpdatePerson( Action ):

            verbose_name = _('Update person')

            def model_run( self, model_context ):
                for person in model_context.get_selection():
                    soc_number = person.social_security_number
                    if soc_number:
                        # assume the social sec number contains the birth date
                        person.birth_date = datetime.date( int(soc_number[0:4]),
                                                           int(soc_number[4:6]),
                                                           int(soc_number[6:8])
                                                           )
                    # delete the email of the person
                    for contact_mechanism in person.contact_mechanisms:
                        model_context.session.delete( contact_mechanism )
                        yield action_steps.DeleteObject( contact_mechanism )
                    # add a new email
                    m = ('email', '%s.%s@example.com'%( person.first_name,
                                                        person.last_name ) )
                    cm = party.ContactMechanism( mechanism = m )
                    pcm = party.PartyContactMechanism( party = person,
                                                       contact_mechanism = cm )
                    # immediately update the GUI
                    yield action_steps.CreateObject( cm )
                    yield action_steps.CreateObject( pcm )
                    yield action_steps.UpdateObject( person )
                # flush the session on finish
                model_context.session.flush()

        # end manual update

        update_person = UpdatePerson()
        for step in update_person.model_run( self.context ):
            step.gui_run( self.gui_context )

        # begin auto update

        class UpdatePerson( Action ):

            verbose_name = _('Update person')

            def model_run( self, model_context ):
                for person in model_context.get_selection():
                    soc_number = person.social_security_number
                    if soc_number:
                        # assume the social sec number contains the birth date
                        person.birth_date = datetime.date( int(soc_number[0:4]),
                                                           int(soc_number[4:6]),
                                                           int(soc_number[6:8])
                                                           )
                        # delete the email of the person
                        for contact_mechanism in person.contact_mechanisms:
                            model_context.session.delete( contact_mechanism )
                        # add a new email
                        m = ('email', '%s.%s@example.com'%( person.first_name,
                                                            person.last_name ) )
                        cm = party.ContactMechanism( mechanism = m )
                        party.PartyContactMechanism( party = person,
                                                    contact_mechanism = cm )
                # flush the session on finish and update the GUI
                yield action_steps.FlushSession( model_context.session )

        # end auto update

        update_person = UpdatePerson()
        for step in update_person.model_run( self.context ):
            step.gui_run( self.gui_context )

    def test_update_progress( self ):
        from camelot.view.controls.progress_dialog import ProgressDialog
        update_progress = action_steps.UpdateProgress( 20, 100, _('Importing data') )
        self.assertTrue( six.text_type( update_progress ) )
        # give the gui context a progress dialog, so it can be updated
        self.gui_context.progress_dialog = ProgressDialog('Progress')
        update_progress.gui_run( self.gui_context )
        # now press the cancel button
        self.gui_context.progress_dialog.cancel()
        with self.assertRaises( CancelRequest ):
            update_progress.gui_run( self.gui_context )

class ListActionsCase( test_model.ExampleModelCase ):
    """Test the standard list actions.
    """

    images_path = test_view.static_images_path

    def setUp( self ):
        super( ListActionsCase, self ).setUp()
        from camelot_example.model import Movie
        from camelot.admin.application_admin import ApplicationAdmin
        self.app_admin = ApplicationAdmin()
        self.context = MockModelContext()
        self.context.obj = Movie.query.first()
        self.context.admin = self.app_admin.get_related_admin( Movie )
        self.gui_context = list_action.ListActionGuiContext()
        self.gui_context.admin = self.app_admin.get_related_admin( Movie )
        self.query_proxy_case = test_proxy.QueryProxyCase('setUp')
        self.query_proxy_case.setUp(self.gui_context.admin)
        table_widget = tableview.AdminTableWidget( self.gui_context.admin )
        table_widget.setModel( self.query_proxy_case.proxy )
        self.gui_context.item_view = table_widget

    def tearDown( self ):
        Session().expunge_all()

    def test_gui_context( self ):
        self.assertTrue( isinstance( self.gui_context.copy(),
                                     list_action.ListActionGuiContext ) )
        model_context = self.gui_context.create_model_context()
        self.assertTrue( isinstance( model_context,
                                     list_action.ListActionModelContext ) )
        list( model_context.get_collection() )
        list( model_context.get_selection() )
        model_context.get_object()

    def test_sqlalchemy_command( self ):
        model_context = self.context
        from camelot.model.batch_job import BatchJobType
        # create a batch job to test with
        bt = BatchJobType( name = 'audit' )
        model_context.session.add( bt )
        bt.flush()
        # begin issue a query through the model_context
        model_context.session.query( BatchJobType ).update( values = {'name':'accounting audit'},
                                                            synchronize_session = 'evaluate' )
        # end issue a query through the model_context
        #
        # the batch job should have changed
        self.assertEqual( bt.name, 'accounting audit' )

    def test_change_row_actions( self ):
        from camelot.test.action import MockListActionGuiContext

        gui_context = MockListActionGuiContext()
        get_state = lambda action:action.get_state( gui_context.create_model_context() )
        to_first = list_action.ToFirstRow()
        to_previous = list_action.ToPreviousRow()
        to_next = list_action.ToNextRow()
        to_last = list_action.ToLastRow()

        # the state does not change when the current row changes,
        # to make the actions usable in the main window toolbar
        to_last.gui_run( gui_context )
        #self.assertFalse( get_state( to_last ).enabled )
        #self.assertFalse( get_state( to_next ).enabled )
        to_previous.gui_run( gui_context )
        #self.assertTrue( get_state( to_last ).enabled )
        #self.assertTrue( get_state( to_next ).enabled )
        to_first.gui_run( gui_context )
        #self.assertFalse( get_state( to_first ).enabled )
        #self.assertFalse( get_state( to_previous ).enabled )
        to_next.gui_run( gui_context )
        #self.assertTrue( get_state( to_first ).enabled )
        #self.assertTrue( get_state( to_previous ).enabled )

    def test_print_preview( self ):
        print_preview = list_action.PrintPreview()
        for step in print_preview.model_run( self.context ):
            dialog = step.render( self.gui_context )
            dialog.show()
            self.grab_widget( dialog )

    def test_export_spreadsheet( self ):
        import xlrd
        export_spreadsheet = list_action.ExportSpreadsheet()
        for step in export_spreadsheet.model_run( self.context ):
            if isinstance( step, action_steps.OpenFile ):
                # see if the generated file can be parsed
                filename = step.get_path()
                xlrd.open_workbook( filename )

    def test_match_names( self ):
        from camelot.view.import_utils import RowData, ColumnMapping, MatchNames

        rows = [['rating', 'name'],
                ['5',      'The empty bitbucket']
                ]
        fields = [field for field, _fa in self.context.admin.get_columns()]
        mapping = ColumnMapping(0, rows)
        self.assertNotEqual( mapping.field, 'rating' )
        
        match_names = MatchNames()
        model_context = MockModelContext()
        model_context.obj = mapping
        model_context.admin = self.context.admin
        
        list(match_names.model_run(model_context))
        self.assertEqual( mapping.field, 'rating' )

    def test_import_from_xls_file( self ):
        self.test_import_from_file( 'import_example.xls' )

    def test_import_from_xlsx_file( self ):
        self.test_import_from_file( 'import_example.xlsx' )

    def test_import_from_file( self, filename = 'import_example.csv' ):
        from camelot.model.party import Person
        example_folder = os.path.join( os.path.dirname(__file__), '..', 'camelot_example' )
        self.context = MockModelContext()
        self.context.obj = Person.query.first() # need an object, to have a
                                                # session
        #self.assertTrue( self.context.obj != None )
        self.context.admin = self.app_admin.get_related_admin( Person )
        import_from_file = list_action.ImportFromFile()
        generator = import_from_file.model_run( self.context )
        for step in generator:
            if isinstance( step, action_steps.SelectFile ):
                generator.send( [ os.path.join( example_folder, filename ) ] )
            if isinstance( step, action_steps.ChangeObject ):
                dialog = step.render( self.gui_context )
                dialog.show()
                self.grab_widget( dialog, suffix = 'column_selection' )
            if isinstance( step, action_steps.ChangeObjects ):
                dialog = step.render()
                dialog.show()
                self.grab_widget( dialog, suffix = 'preview' )
            if isinstance( step, action_steps.MessageBox ):
                dialog = step.render()
                dialog.show()
                self.grab_widget( dialog, suffix = 'confirmation' )

    def test_replace_field_contents( self ):
        replace = list_action.ReplaceFieldContents()
        generator = replace.model_run( self.context )
        for step in generator:
            if isinstance( step, action_steps.ChangeField ):
                dialog = step.render()
                field_editor = dialog.findChild( QtGui.QWidget, 'field_choice' )
                field_editor.set_value( 'rating' )
                dialog.show()
                self.grab_widget( dialog )
                generator.send( ('rating', lambda:3) )

    def test_drag_and_drop( self ):
        from camelot.view.proxy.queryproxy import QueryTableProxy

        class DropAction( Action ):
            pass


        mime_data = QtCore.QMimeData()
        admin = self.context.admin
        admin.drop_action = DropAction()

        proxy = QueryTableProxy(admin)
        proxy.dropMimeData( mime_data,
                            Qt.MoveAction,
                            -1,
                            -1,
                            QtCore.QModelIndex() )

    def test_open_form_view( self ):
        open_form_view_action = list_action.OpenFormView()
        open_form_view_action.gui_run( self.gui_context )

    def test_duplicate_selection( self ):
        query = self.context.admin.entity.query
        pre_duplication = query.count()
        duplicate_selection_action = list_action.DuplicateSelection()
        duplicate_selection_action.model_run( self.context )
        post_duplication = query.count()
        #self.assertEqual( pre_duplication + 1, post_duplication )

    def test_delete_selection( self ):
        session = orm.object_session( self.context.obj )
        self.assertTrue( self.context.obj in session )
        delete_selection_action = list_action.DeleteSelection()
        delete_selection_action.gui_run( self.gui_context )
        list( delete_selection_action.model_run( self.context ) )
        self.assertFalse( self.context.obj in session )

    def test_add_existing_object( self ):
        from camelot_example.model import Movie
        add_existing_object_action = list_action.AddExistingObject()
        generator = add_existing_object_action.model_run( self.gui_context.create_model_context() )
        select_objects_step = generator.next()
        generator.send([Movie(title='Unknown')])
        list(generator)

    def test_add_new_object( self ):
        add_new_object_action = list_action.AddNewObject()
        add_new_object_action.gui_run( self.gui_context )

    def test_remove_selection( self ):
        remove_selection_action = list_action.RemoveSelection()
        list( remove_selection_action.model_run( self.gui_context.create_model_context() ) )

    def test_call_method( self ):
        call_method_action = list_action.CallMethod( 'Call', lambda x:True )
        list( call_method_action.model_run( self.context ) )

class FormActionsCase( test_model.ExampleModelCase ):
    """Test the standard list actions.
    """

    images_path = test_view.static_images_path

    def setUp( self ):
        super( FormActionsCase, self ).setUp()
        from camelot.model.party import Person
        from camelot.admin.application_admin import ApplicationAdmin
        self.query_proxy_case = test_proxy.QueryProxyCase('setUp')
        self.query_proxy_case.setUp()
        self.app_admin = ApplicationAdmin()
        self.model_context = MockModelContext()
        self.model_context.obj = Person.query.first()
        self.model_context.admin = self.app_admin.get_related_admin( Person )
        self.gui_context = form_action.FormActionGuiContext()
        self.gui_context._model = self.query_proxy_case.proxy
        self.gui_context.widget_mapper = QtGui.QDataWidgetMapper()
        self.gui_context.widget_mapper.setModel( self.query_proxy_case.proxy )
        self.gui_context.admin = self.app_admin.get_related_admin( Person )

    def test_gui_context( self ):
        self.assertTrue( isinstance( self.gui_context.copy(),
                                     form_action.FormActionGuiContext ) )
        self.assertTrue( isinstance( self.gui_context.create_model_context(),
                                     form_action.FormActionModelContext ) )

    def test_previous_next( self ):
        previous_action = form_action.ToPreviousForm()
        previous_action.gui_run( self.gui_context )
        next_action = form_action.ToNextForm()
        next_action.gui_run( self.gui_context )
        first_action = form_action.ToFirstForm()
        first_action.gui_run( self.gui_context )
        last_action = form_action.ToLastForm()
        last_action.gui_run( self.gui_context )

    def test_show_history( self ):
        show_history_action = form_action.ShowHistory()
        list( show_history_action.model_run( self.model_context ) )

    def test_close_form( self ):
        close_form_action = form_action.CloseForm()
        list( close_form_action.model_run( self.model_context ) )

class ApplicationCase( test_model.ExampleModelCase ):

    def setUp(self):
        super( ApplicationCase, self ).setUp()
        from camelot.admin.application_admin import ApplicationAdmin
        self.app_admin = ApplicationAdmin()
        self.context = MockModelContext()
        self.context.admin = self.app_admin

    def test_application(self):
        from camelot.admin.action.application import Application
        app = Application(self.app_admin)
        list(app.model_run(self.context))
        
    def test_custom_application(self):
        from camelot.admin.action.application import Application

        # begin custom application
        class CustomApplication(Application):
        
            def model_run( self, model_context ):
                from camelot.view import action_steps
                yield action_steps.UpdateProgress(text='Starting up')
        # end custom application
        
        application = CustomApplication(self.app_admin)
        application.gui_run(GuiContext())

class ApplicationActionsCase( test_model.ExampleModelCase ):
    """Test application actions.
    """

    images_path = test_view.static_images_path

    def setUp(self):
        super( ApplicationActionsCase, self ).setUp()
        from camelot.admin.application_admin import ApplicationAdmin
        from camelot.core.files.storage import Storage
        from camelot.view.workspace import DesktopWorkspace
        self.app_admin = ApplicationAdmin()
        self.context = MockModelContext(session=self.session)
        self.storage = Storage()
        self.gui_context = application_action.ApplicationActionGuiContext()
        self.gui_context.admin = self.app_admin
        self.gui_context.workspace = DesktopWorkspace( self.app_admin, None )

    def test_authentication(self):
        action = application_action.Authentication()
        self.assertTrue( action.get_state(self.context) )
        generator = action.model_run(self.context)
        for step in generator:
            if isinstance(step, action_steps.SelectFile):
                generator.send(test_images)

    def test_refresh( self ):
        from camelot.core.orm import Session
        from camelot.model.party import Person
        refresh_action = application_action.Refresh()
        session = Session()
        session.expunge_all()
        # create objects in various states
        #
        p1 = Person(first_name = u'p1', last_name = u'persistent' )
        p2 = Person(first_name = u'p2', last_name = u'dirty' )
        p3 = Person(first_name = u'p3', last_name = u'deleted' )
        p4 = Person(first_name = u'p4', last_name = u'to be deleted' )
        p5 = Person(first_name = u'p5', last_name = u'detached' )
        p6 = Person(first_name = u'p6', last_name = u'deleted outside session' )
        session.flush()
        p3.delete()
        session.flush()
        p4.delete()
        p2.last_name = u'clean'
        #
        # delete p6 without the session being aware
        #
        person_table = Person.table
        session.execute( person_table.delete().where( person_table.c.party_id == p6.id ) )
        #
        # refresh the session through the action
        #
        list( refresh_action.model_run( self.context ) )
        self.assertEqual( p2.last_name, u'dirty' )

    def test_select_profile(self):
        from . import test_core
        profile_case = test_core.ProfileCase('setUp')
        profile_case.setUp()
        profile_store = profile_case.test_profile_store()
        action = application_action.SelectProfile(profile_store)
        generator = action.model_run(self.context)
        for step in generator:
            if isinstance(step, action_steps.SelectItem):
                generator.send(profile_store.get_last_profile())

    def test_backup_and_restore( self ):
        backup_action = application_action.Backup()
        generator = backup_action.model_run( self.context )
        for step in generator:
            if isinstance( step, action_steps.SelectBackup ):
                dialog = step.render()
                dialog.show()
                self.grab_widget( dialog, suffix = 'backup' )
                generator.send( ('unittest', self.storage) )
        restore_action = application_action.Restore()
        generator = restore_action.model_run( self.context )
        for step in generator:
            if isinstance( step, action_steps.SelectRestore ):
                dialog = step.render()
                dialog.show()
                self.grab_widget( dialog, suffix = 'restore' )
                generator.send( ('unittest', self.storage) )

    def test_show_help( self ):
        show_help_action = application_action.ShowHelp()
        show_help_action.gui_run( self.gui_context )

    def test_change_logging( self ):
        change_logging_action = application_action.ChangeLogging()
        change_logging_action.model_run( self.context )

    def test_open_table_view( self ):
        from camelot.model.party import Person
        person_admin = self.app_admin.get_related_admin( Person )
        open_table_view_action = application_action.OpenTableView( person_admin )
        open_table_view_action.gui_run( self.gui_context )

    def test_open_new_view( self ):
        from camelot.model.party import Person
        person_admin = self.app_admin.get_related_admin( Person )
        open_new_view_action = application_action.OpenNewView( person_admin )
        open_new_view_action.gui_run( self.gui_context )

    def test_change_logging( self ):
        change_logging_action = application_action.ChangeLogging()
        for step in change_logging_action.model_run( self.context ):
            if isinstance( step, action_steps.ChangeObject ):
                step.get_object().level = logging.INFO

    def test_dump_state( self ):
        dump_state = application_action.DumpState()
        list( dump_state.model_run( self.context ) )

    def test_runtime_info( self ):
        runtime_info = application_action.RuntimeInfo()
        list( runtime_info.model_run( self.context ) )

    def test_segmentation_fault( self ):
        segmentation_fault = application_action.SegmentationFault()
        list( segmentation_fault.model_run( self.context ) )

class DocumentActionsCase( ModelThreadTestCase ):
    """Test the standard document actions.
    """

    images_path = test_view.static_images_path

    def setUp( self ):
        ModelThreadTestCase.setUp(self)
        self.gui_context = document_action.DocumentActionGuiContext()
        self.gui_context.document = QtGui.QTextDocument('Hello world')

    def test_gui_context( self ):
        self.assertTrue( isinstance( self.gui_context.copy(),
                                     document_action.DocumentActionGuiContext ) )
        self.assertTrue( isinstance( self.gui_context.create_model_context(),
                                     document_action.DocumentActionModelContext ) )

    def test_edit_document( self ):
        edit_document_action = document_action.EditDocument()
        model_context = self.gui_context.create_model_context()
        list( edit_document_action.model_run( model_context ) )
