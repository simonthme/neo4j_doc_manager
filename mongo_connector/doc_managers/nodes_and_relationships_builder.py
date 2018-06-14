"""
Class that builds Nodes and Relationships
according to a Mongo document.
"""
import re
import logging

from bson.objectid import ObjectId
from mongo_connector.compat import u

LOG = logging.getLogger(__name__)

class NodesAndRelationshipsBuilder(object):
  def __init__(self, doc, doc_type, doc_id, metadata={}, doc_types=[]):
    self.doc_id = doc_id
    self.query_nodes = {}
    self.relationships_query = {}
    self.metadata = metadata or {}
    self.doc_types = doc_types or []
    self.explicit_ids = {}
    self.build_nodes_query(doc_type, doc, doc_id)
    
  def build_nodes_query(self, doc_type, document, id):
    self.doc_types.append(doc_type)
    parameters = {'_id':id}
    if self.is_dict(self.metadata):
      parameters.update(self.metadata) 
    for key in document.keys():
      if self.is_reference(key):
        self.build_node_with_reference(doc_type, key, id, document[key])
        continue
      if self.is_objectid(document[key]):
        parameters.update({key: u(document[key])})
        self.build_node_with_reference(doc_type, key, id, document[key])
        continue
      #TODO: handle arrays of ObjectIds
      if document[key] is None:
        continue
      elif self.is_dict(document[key]):
        self.build_relationships_query(doc_type, key, id, id)
        self.build_nodes_query(key, document[key], id)
      elif self.is_json_array(document[key]):
        for json in self.format_params(document[key]):
          json_key = key + str(document[key].index(json))
          self.build_relationships_query(doc_type, json_key, id, id)
          self.build_nodes_query(json_key, json, id)
      elif self.is_multimensional_array(document[key]):
        parameters.update(self.flatenned_property(key, document[key]))
      else:
        print('TRYBING TO BUILD DA SHIT')
        parameters.update({ key: self.format_params(document[key]) })
    print("DOING IT YAAAAAAAAAAAAAAAYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY")
    query = "CREATE (c:Document:`{doc_type}` {{parameters}})".format(doc_type=doc_type)
    self.query_nodes.update({query: {"parameters":parameters}})

  def format_params(self, params):
    if (type(params) is list):
      return list(filter(None, params))
    return params

  def build_node_with_reference(self, root_type, key, doc_id, document_key):
    if document_key is None:
      return
    doc_type = key.split("_id")[0]

    # ignore _id property of subdocuments
    if not doc_type or doc_type == "":
      return
    parameters = {'_id':document_key}
    statement = "MERGE (d:Document:`{doc_type}` {{ _id: {{parameters}}._id}})".format(doc_type=doc_type)
    self.query_nodes.update({statement: {"parameters":parameters}})
    self.build_relationships_query(root_type, doc_type, doc_id, document_key)
    self.explicit_ids.update({document_key: doc_type})

  def build_node_with_objectid_reference(self, root_type, key, doc_id, document_key):
    if document_key is None:
      return

    parameters = {'_id': u(document_key)}
    statement = "MERGE (d:Document {{_id: {{parameters}}._id}})"
    self.query_nodes.update({statement: {"parameters": parameters}})
    self.build_relationships_query(root_type, 'Document', doc_id, document_key) #FIXME: missing doc_type

  def is_dict(self, doc_key):
    return (type(doc_key) is dict)

  def is_reference(self, key):
    return (re.search(r"_id$", key))

  def is_multimensional_array(self, doc_key):
    return ((type(doc_key) is list) and (doc_key) and (type(doc_key[0]) is list))

  def is_objectid(selfself, doc_key):
    return isinstance(doc_key, ObjectId)

  def flatenned_property(self, key, doc_key):
    parameters = {}
    flattened_list = doc_key
    if ((type(flattened_list[0]) is list) and (flattened_list[0])):
      inner_list = flattened_list[0]
      if (type(inner_list[0]) is list):
        flattened_list = [val for sublist in flattened_list for val in sublist]
        self.flatenned_property(key, flattened_list)
      else: 
        for element in flattened_list:
          element_key = key + str(flattened_list.index(element))
          parameters.update({ element_key: element })
    return parameters

  def is_json_array(self, doc_key):
    return ((type(doc_key) is list) and (doc_key) and (type(doc_key[0]) is dict))


  def build_relationships_query(self, main_type, node_type, doc_id, explicit_id):
    relationship_type = main_type + "_" + node_type
    statement = "MATCH (a:`{main_type}`), (b:`{node_type}`) WHERE a._id={{doc_id}} AND b._id ={{explicit_id}} CREATE (a)-[r:`{relationship_type}`]->(b)".format(main_type=main_type, node_type=node_type, relationship_type=relationship_type)
    params = {"doc_id": doc_id, "explicit_id": explicit_id}
    self.relationships_query.update({statement: params})
