from sqlalchemy import schema, sql
from sqlalchemy.orm import relationship, backref, class_mapper

from . properties import DeferredProperty
from . entity import EntityBase
from . statements import ClassMutator

class Relationship( DeferredProperty ):
    """Generates a one to many or many to one relationship."""

    process_order = 0
    
    def __init__(self, of_kind, inverse=None, *args, **kwargs):
        super( Relationship, self ).__init__()
        self.of_kind = of_kind
        self.inverse_name = inverse
        self._target = None
        self.property = None # sqlalchemy property
        self.backref = None  # sqlalchemy backref
        self.args = args
        self.kwargs = kwargs

    @property
    def target( self ):
        if not self._target:
            if isinstance( self.of_kind, basestring ):
                self._target = self.entity._decl_class_registry[self.of_kind]
            else:
                self._target = self.of_kind
        return self._target
    
    def attach( self, entity, name ):
        super( Relationship, self ).attach( entity, name )
        entity._descriptor.relationships.append( self )
        
    def _config(self, cls, mapper, key):
        """Create a Column with ForeignKey as well as a relationship()."""

        super( Relationship, self )._config( cls, mapper, key )

        pk_target, fk_target = self._get_pk_fk(cls, self.target)
        pk_table = pk_target.__table__
        pk_col = list(pk_table.primary_key)[0]
        
        if pk_target == self.target:
            column_kwargs = self.kwargs.pop( 'column_kwargs', {} )
            column_kwargs.setdefault( 'index', True )
            fk_colname = '%s_%s'%(key, pk_col.key)
            fk_col = schema.Column( fk_colname, pk_col.type, schema.ForeignKey(pk_col), **column_kwargs )
            setattr(fk_target, fk_colname, fk_col)

        #self.kwargs.setdefault( 'collection_class', set )
        self.create_properties()
        
    @property
    def inverse(self):
        if not hasattr(self, '_inverse'):
            if self.inverse_name:
                desc = self.target._descriptor
                inverse = desc.find_relationship(self.inverse_name)
                if inverse is None:
                    raise Exception(
                              "Couldn't find a relationship named '%s' in "
                              "entity '%s' or its parent entities."
                              % (self.inverse_name, self.target.__name__))
                assert self.match_type_of(inverse), \
                    "Relationships '%s' in entity '%s' and '%s' in entity " \
                    "'%s' cannot be inverse of each other because their " \
                    "types do not form a valid combination." % \
                    (self.name, self.entity.__name__,
                     self.inverse_name, self.target.__name__)
            else:
                check_reverse = not self.kwargs.get( 'viewonly', False )
                if issubclass(self.target, EntityBase):
                    inverse = self.target._descriptor.get_inverse_relation(
                        self, check_reverse=check_reverse)
                else:
                    inverse = None
            self._inverse = inverse
            if inverse and not self.kwargs.get('viewonly', False):
                inverse._inverse = self

        return self._inverse
    
    def match_type_of(self, other):
        return False
    
    def is_inverse( self, other ):
        # viewonly relationships are not symmetrical: a viewonly relationship
        # should have exactly one inverse (a ManyToOne relationship), but that
        # inverse shouldn't have the viewonly relationship as its inverse.
        return not other.kwargs.get('viewonly', False) and \
               other is not self and \
               self.match_type_of( other ) and \
               self.entity == other.target and \
               other.entity == self.target and \
               (self.inverse_name == other.name or not self.inverse_name) and \
               (other.inverse_name == self.name or not other.inverse_name)
    
    def create_properties( self ):
        if self.property or self.backref:
            return

        kwargs = self.get_prop_kwargs()
        # viewonly relationships need to create "standalone" relations (ie
        # shouldn't be a backref of another relation).
        if self.inverse and not kwargs.get( 'viewonly', False ):
            # check if the inverse was already processed (and thus has already
            # defined a backref we can use)
            if self.inverse.backref:
                # let the user override the backref argument
                if 'backref' not in kwargs:
                    kwargs['backref'] = self.inverse.backref
            else:
                # SQLAlchemy doesn't like when 'secondary' is both defined on
                # the relation and the backref
                kwargs.pop('secondary', None)

                # define backref for use by the inverse
                self.backref = backref( self.name, **kwargs )
                return
        
        self.property = relationship( self.target, **kwargs )
        setattr( self.entity, self.name, self.property )

class OneToOne( Relationship ):

    uselist = False
    process_order = 2
    
    def __init__(self, of_kind, filter=None, *args, **kwargs):
        self.filter = filter
        if filter is not None:
            # We set viewonly to True by default for filtered relationships,
            # unless manually overridden.
            # This is not strictly necessary, as SQLAlchemy allows non viewonly
            # relationships with a custom join/filter. The example at:
            # SADOCS/05/mappers.html#advdatamapping_relation_customjoin
            # is not viewonly. Those relationships can be used as if the extra
            # filter wasn't present when inserting. This can lead to a
            # confusing behavior (if you insert data which doesn't match the
            # extra criterion it'll get inserted anyway but you won't see it
            # when you query back the attribute after a round-trip to the
            # database).
            if 'viewonly' not in kwargs:
                kwargs['viewonly'] = True
        super(OneToOne, self).__init__(of_kind, *args, **kwargs)
    
    def match_type_of(self, other):
        return isinstance(other, ManyToOne)
    
    def get_prop_kwargs(self):
        kwargs = {'uselist': self.uselist}

        #TODO: for now, we don't break any test if we remove those 2 lines.
        # So, we should either complete the selfref test to prove that they
        # are indeed useful, or remove them. It might be they are indeed
        # useless because the remote_side is already setup in the other way
        # (ManyToOne).
        if self.entity.table is self.target.table:
            #FIXME: IF this code is of any use, it will probably break for
            # autoloaded tables
            kwargs['remote_side'] = self.inverse.foreign_key

        # Contrary to ManyToMany relationships, we need to specify the join
        # clauses even if this relationship is not self-referencial because
        # there could be several ManyToOne from the target class to us.
        joinclauses = self.inverse.primaryjoin_clauses
        if self.filter:
            # We need to make a copy of the joinclauses, to not add the filter
            # on the backref
            joinclauses = joinclauses[:] + [self.filter(self.target.table.c)]
        if joinclauses:
            kwargs['primaryjoin'] = sql.and_(*joinclauses)

        kwargs.update(self.kwargs)

        return kwargs    
    
class OneToMany( OneToOne ):
    """Generates a one to many relationship."""
    uselist = True

    def _get_pk_fk( self, cls, target_cls ):
        return cls, target_cls

class ManyToOne( Relationship ):
    """Generates a many to one relationship."""

    process_order = 1
    
    def __init__(self, of_kind,
                 column_kwargs=None,
                 colname=None, required=None, primary_key=None,
                 field=None,
                 constraint_kwargs=None,
                 use_alter=None, ondelete=None, onupdate=None,
                 target_column=None,
                 *args, **kwargs):

        # 1) handle column-related args

        # check that the column arguments don't conflict
        assert not (field and (column_kwargs or colname)), \
               "ManyToOne can accept the 'field' argument or column " \
               "arguments ('colname' or 'column_kwargs') but not both!"

        if colname and not isinstance(colname, list):
            colname = [colname]
        self.colname = colname or []

        column_kwargs = column_kwargs or {}
        # kwargs go by default to the relation(), so we need to manually
        # extract those targeting the Column
        if required is not None:
            column_kwargs['nullable'] = not required
        if primary_key is not None:
            column_kwargs['primary_key'] = primary_key
        # by default, created columns will have an index.
        column_kwargs.setdefault('index', True)
        self.column_kwargs = column_kwargs

        if field and not isinstance(field, list):
            field = [field]
        self.field = field or []

        # 2) handle constraint kwargs
        constraint_kwargs = constraint_kwargs or {}
        if use_alter is not None:
            constraint_kwargs['use_alter'] = use_alter
        if ondelete is not None:
            constraint_kwargs['ondelete'] = ondelete
        if onupdate is not None:
            constraint_kwargs['onupdate'] = onupdate
        self.constraint_kwargs = constraint_kwargs

        # 3) misc arguments
        if target_column and not isinstance( target_column, list ):
            target_column = [target_column]
        self.target_column = target_column

        self.foreign_key = []
        self.primaryjoin_clauses = []

        super(ManyToOne, self).__init__( of_kind, *args, **kwargs )    
    
    def _get_pk_fk( self, cls, target_cls ):
        return target_cls, cls
    
    def get_prop_kwargs(self):
        kwargs = {'uselist': False}

        if self.entity.table is self.target_table:
            # this is needed because otherwise SA has no way to know what is
            # the direction of the relationship since both columns present in
            # the primaryjoin belong to the same table. In other words, it is
            # necessary to know if this particular relation
            # is the many-to-one side, or the one-to-xxx side. The foreignkey
            # doesn't help in this case.
            kwargs['remote_side'] = \
                [col for col in self.target_table.primary_key.columns]

        if self.primaryjoin_clauses:
            kwargs['primaryjoin'] = sql.and_(*self.primaryjoin_clauses)

        kwargs.update(self.kwargs)

        return kwargs
    
    def match_type_of(self, other):
        return isinstance(other, (OneToMany, OneToOne))    
    
    @property
    def target_table( self ):
        return class_mapper( self.target ).local_table    

class ManyToMany( DeferredProperty ):
    """Generates a many to many relationship."""

    process_order = 3
    
    def __init__( self, target, tablename, local_colname, remote_colname, **kw ):
        self.target = target
        self.tablename = tablename
        self.local = local_colname
        self.remote = remote_colname
        self.kw = kw

    def _config(self, cls, mapper, key):
        """Create an association table between parent/target
        as well as a relationship()."""

        target_cls = cls._decl_class_registry[self.target]
        local_pk = list(cls.__table__.primary_key)[0]
        target_pk = list(target_cls.__table__.primary_key)[0]
        t = schema.Table(
                self.tablename,
                cls.metadata,
                schema.Column(self.local, schema.ForeignKey(local_pk), primary_key=True),
                schema.Column(self.remote, schema.ForeignKey(target_pk), primary_key=True),
                keep_existing=True
            )
        rel = relationship(target_cls,
                secondary=t,
                # use list instead of set because collection proxy does not
                # work with sets
                collection_class=self.kw.get('collection_class', list)
            )
        setattr(cls, key, rel)
        self._setup_reverse(key, rel, target_cls)
        
    def match_type_of(self, other):
        return isinstance(other, ManyToMany) 
    
class belongs_to( ClassMutator ):

    def process( self, entity_dict, name, *args, **kwargs ):
        entity_dict[ name ] = ManyToOne( *args, **kwargs )

class has_one( ClassMutator ):

    def process( self, entity_dict, name, *args, **kwargs ):
        entity_dict[ name ] = OneToOne( *args, **kwargs )

class has_many( ClassMutator ):
    
    def process( self, entity_dict, name, *args, **kwargs ):
        entity_dict[ name ] = OneToMany( *args, **kwargs )

class has_and_belongs_to_many( ClassMutator ):

    def process( self, entity_dict, name, *args, **kwargs ):
        entity_dict[ name ] = ManyToMany( *args, **kwargs )
