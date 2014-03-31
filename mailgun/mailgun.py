import os
import posixpath
import requests
import simplejson as json

from email.utils import parsedate_tz

def ser_bool(val):
    if isinstance(val, basestring):
        val = val.lower() not in ('false', 'no')
    return 'yes' if val else 'no'

def deser_bool(val):
    return val in (True, 'yes')

class Mailgun(object):
    def __init__(self, apiurl=None, apikey=None, domain=None):
        self.apiurl = apiurl or os.getenv('MAILGUN_API_URL')
        self.domain = domain or os.getenv('MAILGUN_DOMAIN', '')
        apikey = apikey or os.getenv('MAILGUN_API_KEY')
        self.auth = ('api', apikey)

    def url(self, res):
        return posixpath.join(self.apiurl, *res)

    def get(self, url, **kwargs):
        response = requests.get(url, auth=self.auth, **kwargs)
        response.raise_for_status()
        return response.json()
    
    def post(self, url, **kwargs):
        response = requests.post(url, auth=self.auth, **kwargs)
        response.raise_for_status()
        return response.json()
    
    def put(self, url, **kwargs):
        response = requests.put(url, auth=self.auth, **kwargs)
        response.raise_for_status()
        return response.json()
    
    def delete(self, url, **kwargs):
        response = requests.delete(url, auth=self.auth)
        response.raise_for_status()
        return response.json()

    def send_message(self, from_address, to,
                            subject=None,
                            text=None,
                            html=None,
                            tracking=False):
        data = {'from': from_address, 'to': to}
        if subject is not None: data['subject'] = subject
        if text is not None: data['text'] = text
        if html is not None: data['html'] = html
        data['o:tracking'] = tracking
        url = self.url((self.domain, 'messages'))
        return self.post(url, data=data)

    def new_list(self, address,
                        name=None,
                        description=None,
                        access_level=None):
        data = {'address': address}
        if name:
            data['name'] = name
        if description:
            data['description'] = description
        if access_level:
            data['access_level'] = access_level
        response = self.post(self.url(('lists',)), data=data)
        return MailingList(self, response['list'])

    def lists(self, skip=None, limit=None):
        params = {}
        if limit:
            params['limit'] = limit
        if skip:
            params['skip'] = skip
        response = self.get(self.url(('lists',)), params=params)
        return [MailingList(self, ld) for ld in response['items']]

    def get_list(self, address):
        response = self.get(self.url(('lists', address)))
        return MailingList(self, response['list'])

class Resource(object):
    """
    Generic interface to api resources.
    Required subclass attributes:

        fields: a dict of data fields.
            the dict values are 3-tuples containing:
            (deserializer, serializer (or None), default value)

        apipath: the path parts passed to Mailgun.url()

        pk_field: which field identifies the resource
            (also passed to Mailgun.url())
    """
    def __init__(self, conn, data, apipath=None):
        if apipath:
            self.apipath = apipath
        self.conn = conn
        self.deser(data)

    def pk(self):
        return getattr(self, self.pk_field)

    def path(self, *res):
        return self._path + res

    def deser(self, data):
        for key, (deser, ser, default) in self.fields.iteritems():
            setattr(self, key, deser(data.get(key, default)))
        self._path = tuple(self.apipath) + (self.pk(),)

    def ser(self):
        data = {}
        for key, (deser, ser, default) in self.fields.iteritems():
            if ser:
                data[key] = ser(getattr(self, key, default))
        return data

    def get(self):
        url = self.conn.url(self.path())
        return self.conn.get(url)

    def put(self):
        url = self.conn.url(self.path())
        return self.conn.put(url, data=self.ser())

    def delete(self):
        url = self.conn.url(self.path())
        return self.conn.delete(url)
        

class MailingList(Resource):
    apipath = 'lists',
    pk_field = 'address'
    fields = {
            'address': (str, str, ''),
            'name': (str, str, ''),
            'description': (str, str, ''),
            'members_count': (int, None, 0),
            'created_at': (parsedate_tz, None, ''),
            'access_level': (str, str, 'readonly'),
        }

    def __unicode__(self):
        if self.name:
            '%s <%s>' % (self.name, self.address)
        else:
            return self.address

    def get(self):
        self.deser(super(MailingList, self).get()['list'])

    def put(self):
        self.deser(super(MailingList, self).put()['list'])

    def delete(self):
        response = super(MailingList, self).delete()
        return response['message']


    def new_member(self, address, name=None, vars=None, subscribed=None, upsert=None):
        path = self.path('members')
        url = self.conn.url(path)
        data = {'address': address}
        if name:
            data['name'] = name
        if vars is not None:
            data['vars'] = json.dumps(vars)
        if subscribed is not None:
            data['subscribed'] = ser_bool(subscribed)
        if upsert is not None:
            if isinstance(upsert, basestring):
                upsert = upsert.lower() not in ('false', 'no')
            data['upsert'] = 'yes' if upsert else 'no'

        response = self.conn.post(url, data=data)
        return MailingListMember(self.conn, response['member'], apipath=path)

    def add_members(self, members, subscribed=None):
        path = self.path('members.json')
        url = self.conn.url(path)
        data = {'members': json.dumps(members)}
        if subscribed is not None:
            data['subscribed'] = ser_bool(subscribed)
        response = self.conn.post(url, data=data)
        self.deser(response['list'])

    def members(self, skip=None, limit=None, subscribed=None):
        path = self.path('members')
        url = self.conn.url(path)
        params = {}
        if limit:
            params['limit'] = limit
        if skip:
            params['skip'] = skip
        if subscribed is not None:
            params['subscribed'] = ser_bool(subscribed)
        response = self.conn.get(url, params=params)
        return [MailingListMember(self.conn, d, path) for d in response['items']]

    def stats(self):
        path = self.path('stats')
        url = self.conn.url(path)
        return self.conn.get(url)


class MailingListMember(Resource):
    pk_field = 'address'
    fields = {
            'address': (str, str, ''),
            'name': (str, str, ''),
            'subscribed': (deser_bool, ser_bool, True),
            'vars': (dict, dict, {}),
        }

    def get(self):
        self.deser(super(MailingListMember, self).get()['member'])

    def put(self):
        self.deser(super(MailingListMember, self).put()['member'])

    def delete(self):
        response = super(MailingListMember, self).delete()
        return response['message']

