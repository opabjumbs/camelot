#  ============================================================================
#
#  Copyright (C) 2007-2013 Conceptive Engineering bvba. All rights reserved.
#  www.conceptive.be / info@conceptive.be
#
#  This file is part of the Camelot Library.
#
#  This file may be used under the terms of the GNU General Public
#  License version 2.0 as published by the Free Software Foundation
#  and appearing in the file license.txt included in the packaging of
#  this file.  Please review this information to ensure GNU
#  General Public Licensing requirements will be met.
#
#  If you are unsure which license is appropriate for your use, please
#  visit www.python-camelot.com or contact info@conceptive.be
#
#  This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
#  WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
#
#  For use of this library in commercial applications, please contact
#  info@conceptive.be
#
#  ============================================================================

"""ModelContext, GuiContext and Actions that are used in the context of
editing a document.
"""

from .base import Action
from .application_action import ( ApplicationActionGuiContext, 
                                  ApplicationActionModelContext )
from ...core.utils import ugettext_lazy as _
from ...view.art import Icon

class DocumentActionModelContext( ApplicationActionModelContext ):
    
    def __init__( self ):
        super( DocumentActionModelContext, self ).__init__()
        self.document = None
    
class DocumentActionGuiContext( ApplicationActionGuiContext ):
    """The GUI context for an :class:`camelot.admin.action.ApplicationActionGuiContext`.
    On top of  the attributes of the 
    :class:`camelot.admin.action.base.ApplicationActionGuiContext`, this context 
    contains :
    
    .. attribute:: document
    
        the :class:`QtGui.QTextDocument` upon which this action is acting

    .. attribute:: view
    
        the view that displays the document
        
    """
    
    model_context = DocumentActionModelContext
    
    def __init__( self ):
        super( DocumentActionGuiContext, self ).__init__()
        self.document = None
        self.view = None
        
    def copy( self, base_class=None ):
        new_context = super( DocumentActionGuiContext, self ).copy( base_class )
        new_context.document = self.document
        new_context.view = self.view
        return new_context
    
    def create_model_context( self ):
        context = super( DocumentActionGuiContext, self ).create_model_context()
        context.document = self.document
        return context
    
class EditDocument( Action ):
    
    verbose_name = _('Edit')
    icon = Icon('tango/16x16/apps/accessories-text-editor.png')
    tooltip = _('Edit this document')
    
    def model_run( self, model_context ):
        from ...view import action_steps
        edit = action_steps.EditTextDocument(model_context.document)
        yield edit
        yield action_steps.UpdatePrintPreview()
