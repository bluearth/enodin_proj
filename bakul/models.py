from django.db import models
from django.core.exceptions import FieldError
from treebeard.al_tree import AL_Node
from polymorphic import PolymorphicModel, ShowFieldTypeAndContent
import uuid as uuid_impl # Renamed to avoid clash with field names.

DEFAULT_NODE_TYPE = u'bakul:node'
DEFAULT_PROPERTY_TYPE = u'bakul:property'

def print_qset(qset):
    """
    Utility function to print queryset items in tabular format
    :param qset: a query set
    """
    #FIXME assert that qset is instance of django QuerySet
    for item in qset:
        print item


def get_uuid():
    """
    Generates UUID4

    :returns: UUID in 32 char hex format
    """
    return unicode(uuid_impl.uuid4().get_hex())

class NodeType(models.Model):
    name = models.CharField(max_length = 50, null = False, editable = True, db_index = True)
    extends = models.CharField(max_length = 50, null = True, editable = True, db_index = True)
    author = models.CharField(max_length = 50, null = True, editable = True, db_index = False)
    description = models.TextField(max_length = 50, null = True, editable = True, db_index = False)
    short_description = models.TextField(max_length = 50, null = True, editable = True, db_index = False)
    viewer = models.CharField(max_length = 100, null = True, editable = True, db_index = False)

    def __unicode__(self):
        return u"{'id':'%s', 'name':'%s', 'extends':'%s', 'author':'%s','description':'%s','viewer':'%s'}" % (
            self.id, self.name, self.extends, self.author, self.description, self. viewer)

    def get_fields(self):
        return []


class NodeTypeField(models.Model):
    name = models.CharField(max_length = 50, null = False, editable = True, db_index = True)
    field_type = models.ForeignKey('FieldType', null = False)
    node_type = models.ForeignKey('NodeType', null = False)

    def __unicode__(self):
        return u"{'id':'%s', 'name':'%s', 'type_name':'%s', 'doctype':'%s'}" % (
            self.id, self.name, self.field_type.name, self.node_type.name)

class FieldType(models.Model):
    name = models.CharField(max_length = 50, null = False, editable = False, db_index = True)
    classname = models.CharField(max_length = 100, null = False, editable = False)

#   def __unicode__(self):
#       return u"{'id':'%s', 'name':'%s', 'classname':'%s'}" % (
#           self.id, self.name, self.classname)

    def __unicode__(self):
        return self.name

class Item(PolymorphicModel, ShowFieldTypeAndContent, AL_Node):
    """
    Abstract super class for Node and Property.
    """
    uuid = models.CharField(max_length = 32, null = False, default = get_uuid, db_index = True)
    name = models.CharField(max_length = 50, null = True, default = '', db_index = True)
    parent = models.ForeignKey('self', related_name='children_set', null=True,
        db_index=True)
    # Enable node_order_by only if sib_order is not used
    node_order_by = ['date_created', 'date_modified']
    # Enable sib_order only if node_order_by is not used
    #sib_order = models.PositiveIntegerField()
    # From ShowFieldTypeAndContent. Limits field content printout
    polymorphic_showfield_max_field_width = 20

#   def __unicode__(self):
#       return u'{id: %d, uuid : %s}' % (self.id, self.uuid)

    def dump_tree(self, depth=1):
        """
        Dumps the tree formatted as, well..., tree.
        :param depth: maximum depth to traverse. If ommitted defaults to 1
                
        """
        print u'- <%d, %s>' % (self.id, self.uuid)
        if depth > 0:
            children = self.get_children()
            for ch in children:
                print u' ',
                ch.dump_tree(depth - 1)
    
    def get_children(self):
        if issubclass(self.__class__, AL_Node):
            return Item.objects.filter(parent = self)

        elif issubclass(self.__class__, NS_Node):
            if self.is_leaf():
                return Item.objects.none()          
            return Item.get_tree(self).exclude(pk=self.id).filter(depth=self.depth + 1)

        elif issubclass(self.__class__, MP_Node):
            if self.is_leaf():
                return Item.objects.none()          
            return Item.objects.filter(depth=self.depth + 1,
                path__range=self._get_children_path_interval(self.path))

#   class Meta:
#       abstract = True

class Node(Item):
    date_created = models.DateTimeField(null = False, auto_now_add = True)
    date_modified = models.DateTimeField(null = False, auto_now = True)
    node_type = models.ForeignKey('NodeType', null = True)

    def has_property(self, prop_name, narrow_check=False):
        """
        Test if this Node has property(es) prop_name. prop_name can be a unicode string
        or a list of string. 

        Current implementation only checks against this node's NodeType.
        :param prop_name: The name of property to be checked or a list of names
        :param narrow_check: If True means only checks against this node's NodeType.
            False means search for all Property children of this node. 
        :returns: True if this Node's NodeType has property with the name 'prop_name', 
            False otherwise. Returns a list of statuses if prop_name is a list.
        """         
        if narrow_check:
            #TODO implement narrow check
            raise NotImplementedError
        else:

            if (type(prop_name) == list):
                # If prop_name is a list...
                # Narrow down search, make use of cache
                avail_prop = self.get_children().instance_of(Property).filter(name__in = prop_name)
                #avail_prop = Property.objects.filter(parent__id = self.id, name__in = prop_name)
                has_status = []
                for pn in prop_name:
                    try: 
                        if avail_prop.get(name = pn): has_status.append(True)
                    except Item.DoesNotExist: has_status.append(False)
            
                assert len(has_status) == len(prop_name), "Returned statuses must be as much as passed prop names."
                return has_status
        
            else:
                prop_child = Property.objects.filter(parent__id = self.id, name = prop_name)
                if prop_child : return True
                else: return False

    def set_property(self, **kwargs):       
        """
        Set property of this node. property names will be checked for existance a
        and values will be checked for type compatibility
        """
        # Node ini harus sudah tersave sebelum bisa tambah property
        if not self.id: raise ValueError("Node must be saved before adding properties.")

        if kwargs.has_key("identifier") or kwargs.has_key("date_created") or kwargs.has_key("date_modified"):
            # TODO bisakah basic Node property di ubah2?
            # ...untuk sekarang, buang saja dan abaikan dulu
            kwargs.pop("identifier")
            kwargs.pop("date_created")
            kwargs.pop("date_modified")
        
        # TODO Perlukah sanity checking kwargs lebih jauh lagi?
        candidate_props = kwargs.keys()
        candidate_status = self.has_property(candidate_props)
        # Manfaatkan caching dengan mengambil properties yg sudah pasti ada dulu
        exists_props = self.properties_qset().filter(name__in = candidate_props)
        for i in range(0,len(candidate_status)):
            prop_name = candidate_props[i]
            prop_value = kwargs[prop_name]
            # Berdasarkan candidate_status ke-i...
            if candidate_status[i]:
                # ...node ini sudah punya property bernama candidate_props[i], tinggal men-set valuenya saja
                prop = exists_props[i]
                print prop.value.__class__
                ##
                # FIXME I'm not sure if this is the best wayt to do type compatibility check
                ##
                self.__type_check(prop.value, prop_value)
                if type(prop_value) == str: prop_value = unicode(prop_value)    # Tweak for str v unicode
                if type(prop.value) != type(prop_value):
                    raise ValueError(u"%s, Incompatible value type for '%s'. Expecting '%s' but got '%s'" % (self.node_type.name, prop_name, type(prop.value),  type(prop_value)))
    
                prop.value = prop_value
                prop.save()
            
            else:
                # ...node ini belum punya property bernama candidate_prop[i], 
                # silently ignore? raise ValueError?
                raise ValueError(u"%s, Property '%s' not found." % (self.node_type.name, prop_name))
    
    def set_node_type(self, node_type):     
        ##
        # Changing node type is not currently supported.
        ##
        if self.node_type and (self.node_type.name != DEFAULT_NODE_TYPE):
            raise FieldError(u"This node already has nodetype: %s." % self.node_type.name )
        
        field_list = None

        if (type(node_type) == str): node_type= unicode(node_type) # str to unicode tweak
        if (type(node_type) == unicode):
            # Jika node_type diberi dalam bentuk string...
            try:
                node_type_obj = NodeType.objects.get(name = node_type)
            except NodeType.DoesNotExist:
                raise ValueError(u"NodeType '%s' is not registered." % node_type)
        else:
            # Jika node_type diberi sudah dalam bentuk instance...
            node_type_obj = nodeType

        field_list = node_type_obj.nodetypefield_set.all()
        mod_name = self.__module__
        #FIXME should be executed within transaction context
        for field in field_list:
            klass_name = field.field_type.classname
            mod = __import__(mod_name, globals(), locals(), [klass_name])
            klass = getattr(mod, klass_name)
            prop = klass.add_root(name = field.name)
            prop.move(self, pos = 'sorted-child')
        
        # Last, set the node_type field
        self.node_type = node_type_obj
        self.save()

    def get_value(self, prop_name):
        raise NotImplemented

        if not self.has_property(prop_name):
            raise ValueError(u"Property '%s' not found." % prop_name)

        prop = Property.objects.filter(parent__id = self.id).get(name = prop_name)
        assert prop is not None, u"This node sould have property '%s'" % prop_name
        return prop.value

    def properties_qset(self):
        """
        Get a query set containing all Properties of this node
        :returns: Django queryset of all property of this node
        """
        return self.get_children().instance_of(Property)
    
    def properties(self):
        """
        Get this node's properties as python dictionary
        :returns: this node's properties
        """
        prop_child = self.get_children().instance_of(Property)
        d = {}
        for p in prop_child:
            d[p.name] = p.value

        return d

    def property(self, prop_name):
        return self.properties_qset().get(name = prop_name)

    

class Property(Item):
    pass
#   def __unicode__(self):
#       return u"{'name':'%s', 'value':'%s' }" % (self.name, self.value)

#   class Meta:
#       abstract = True

class StringProperty(Property):
    value = models.CharField(max_length = 50, null = True, default = '')

class BooleanProperty(Property):
    value = models.BooleanField(null = False, default = False)

class NullBooleanProperty(Property):
    value = models.NullBooleanField(null = True, default = False)

class DateProperty(Property):
    value = models.DateField(null = True, auto_now = True)

class DateTimeProperty(Property):
    value = models.DateTimeField(null = True, auto_now = True)

class DecimalProperty(Property):
    ##
    #FIXME I just chose arbitrary limit for decimal_places and max_digit. 
    value = models.DecimalField(decimal_places = 10, max_digits = 30, null = True, default = 0.0)

class FloatProperty(Property):
    value = models.FloatField(null = True, default = 0.0)

class IntegerProperty(Property):
    value = models.IntegerField(null = True, default = 0)

class TextProperty(Property):
    value = models.TextField(null = True, default = '')

class TimeProperty(Property):
    value = models.TimeField(null = True, auto_now = True)


class Repository(models.Model):
    name = models.CharField(max_length = 50, null = False, db_index = True, unique = True)
    uuid = models.CharField(max_length = 32, null = False, default = get_uuid, db_index = True, unique = True)
    registered_types = models.ManyToManyField('NodeType')
    root_node = models.OneToOneField('Node', null = False)

    def __unicode__(self):
        return u"{'name' : '%s', 'uuid' : '%s'}" %
            (self.name, self.uuid)

    def create_workspace(self, ws_name, path = None):
        """
        Create a new workspace in this repository
        :param ws_name: The new workspace name.
        :param path: Path where the workspace will be created
        :returns: created repository
        """
        raise NotImplementedError


class Workspace(Node):
    root_node = models.ForeignKey('Node', null = False)
    repository = models.ForeignKey('Repository', null = False)
    current_node = root_node

    def cwd(self, path):
        """
        Change current working node
        :param path: new working node's path
        :returns: new working node
        """
        raise NotImplementedError

    def pwd(self):
        """
        :returns: Current working node
        """
        raise NotImplementedError

    def create_node(self, node_type):
        """
        Creates new node as child of current working node
        :params node_type: the new node's node type
        :returns: the created node
        """
        raise NotImplementedError

    def get_node(self, path):
        """
        Fetch node in path <code>path</code>
        :params path: The node's path
        :returns: The node
        """
        raise NotImplementedError

    def print_cwd(self):
        raise NotImplementedError

    def print_path(self):
        raise NotImplementedError



