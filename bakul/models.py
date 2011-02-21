from django.db import models
from treebeard.al_tree import AL_Node
import uuid as uuid_impl # Renamed to avoid clash with field names.

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
class Item(AL_Node):
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

    def __unicode__(self):
        return u'{id: %d, uuid : %s}' % (self.id, self.uuid)

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
    
    class Meta:
        abstract = True

class Node(Item):
    date_created = models.DateTimeField(null = False, auto_now_add = True)
    date_modified = models.DateTimeField(null = False, auto_now = True)
    node_type = models.ForeignKey('NodeType', null = False)

    def has_property(self, prop_name):
        """
        Test if this Node has property(es) prop_name. prop_name can be a unicode string
        or a list of string.
        :return: True if this Node has property with the name 'prop_name', False otherwise, 
        or a list of status if prop_name is a list of property names.
        """         
        if (type(prop_name) == list):
            # If prop_name is a list...
            # Narrow down search, make use of cache
            avail_prop = Property.objects.filter(parent__id = self.id, name__in = prop_name)
            has_status = []
            for pn in prop_name:
                try: 
                    if avail_prop.get(name = pn): has_status.append(True)
                except Property.DoesNotExist: has_status.append(False)
            
            assert len(has_status) == len(prop_name), "Returned statuses must be as much as passed prop names."
            return has_status
        
        else:
            prop_child = Property.objects.filter(parent__id = self.id, name = prop_name)
            if prop_child : return True
            return False

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
        exists_props = Property.objects.filter(parent__id = self.id, name__in = candidate_props)

        for i in range(0,len(candidate_status)):
            prop_name = candidate_props[i]
            prop_value = kwargs[prop_name]
            prop = None
            # Berdasarkan candidate_status ke-i...
            if candidate_status[i]:
                # ...node ini sudah punya property bernama candidate_props[i], tinggal men-set valuenya saja
                prop = exists_props.filter(parent__id = self.id).get(name = prop_name)
                ##
                # FIXME I'm not sure if this is the best wayt to do type compatibility check
                ##
                if type(prop_value) == str: prop_value = unicode(prop_value)    # Tweak for str v unicode
                if type(prop.value) != type(prop_value):
                    raise ValueError(u"Incompatible value type for '%s'. Expecting '%s' but got '%s'" % (prop_name, type(prop.value),  type(value)))
        
                prop.value = prop_value
                prop.save()
            
            else:
                # ...node ini belum punya property bernama candidate_prop[i], 
                # silently ignore? raise ValueError?
                raise ValueError(u"Property '%s' not found." % prop_name)           

    #def set_property(self, prop_name, value):
    #   if not self.has_property(prop_name):
    #       raise ValueError(u"Property '%s' not found." % prop_name)
    #
    #   prop = Property.objects.filter(parent__id = self.id).get(name = prop_name)
    #   assert prop is not None, u"This node sould have property '%s'" % prop_name
    #
    #   ##
    #   # FIXME I'm not sure if this is the best wayt to do type compatibility check
    #   ##
    #
    #   # Tweak for str v unicode
    #   if type(value) == str: value = unicode(value)
    #   if type(prop.value) != type(value):
    #       raise ValueError(u"Incompatible value type. Expecting %s but got %s" % (type(prop.value),  type(value)))
    #   
    #   prop.value = value
    #   prop.save()

    def set_node_type(self, node_type):     
        ##
        # FIXME Sebelum saya dapat ide untuk mengimplementasikan node type inheritence
        # sebuah node yang sudah memiliki tipe tidak bisa diubah lagi tipenya lebih lanjut
        ##
        if self.node_type:
            raise FieldError(u"This node already has nodetype: %s." % self.node_type.name )
        
        mod_name = self.__module__
        field_list = None

        if (type(node_type) == str): node_type= unicode(node_type) # str to unicode tweak
        if (type(node_type) == unicode):
            # Jika node_type diberi dalam bentuk string...
            try:
                node_type_obj = NodeType.objects.get(name = node_type)
            except NodeType.DoesNotExists:
                raise ValueError(u"No NodeType with name '%s' registered." % node_type)
        else:
            # Jika node_type diberi sudah dalam bentuk instance...
            node_type_obj = nodeType

        field_list = node_type_obj.nodetypefield_set.all()
        for field in field_list:
            type_klass_name = u'%s.%s' % (mod_name, field.field_type.classname)
            self.add_child(type_name = type_klass_name, name = field.name)
        
        self.node_type = node_type_obj


    def get_value(self, prop_name):
            if not self.has_property(prop_name):
                raise ValueError(u"Property '%s' not found." % prop_name)

            prop = Property.objects.filter(parent__id = self.id).get(name = prop_name)
            assert prop is not None, u"This node sould have property '%s'" % prop_name
            return prop.value

    def properties(self):
        prop_child = Property.objects.filter(parent__id = self.id)
        return prop_child
    
    def prop_as_dict(self):
        prop_child = Property.objects.filter(parent = self)
        d = {}
        for p in prop_child:
            d[p.name] = p.value

        return d
    
    def get_path(self):
        if self.parent == None:
            return u'/'
        
        return self.parent.get_path() + u'%d/' % self.id
        pass        


class Property(Item):

    def __unicode__(self):
        return u"{'name':'%s', 'value':'%s' }" % (self.name, self.value)

    class Meta:
        abstract = True

class StringProperty(Property):
    value = models.CharField(max_length = 50, null = True)

class BooleanProperty(Property):
    value = models.BooleanField(null = False)

class NullBooleanProperty(Property):
    value = models.NullBooleanField(null = True)

class DateProperty(Property):
    value = models.DateField(null = True)

class DateTimeProperty(Property):
    value = models.DateTimeField(null = True)

class DecimalProperty(Property):
    ##
    #FIXME I just chose arbitrary limit for decimal_places and max_digit. 
    value = models.DecimalField(decimal_places = 10, max_digits = 30, null = True)

class FloatProperty(Property):
    value = models.FloatField(null = True)

class IntegerProperty(Property):
    value = models.IntegerField(null = True)

class TextProperty(Property):
    value = models.TextField(null = True)

class TimeProperty(Property):
    value = models.TimeField(null = True)



