from mock import patch, DEFAULT

import simplejson as json

from django.test import TestCase
from .. import mailgun

@patch.multiple('requests', get=DEFAULT, post=DEFAULT, put=DEFAULT, delete=DEFAULT)
class TestMailgun(TestCase):
    def setUp(self):
        self.mg = mailgun.Mailgun(
                            apiurl='https://mailgun.example.com/',
                            apikey='api-key',
                            domain='domain.example.com',
                        )

    def test_init(self, get, post, put, delete):
        self.assertEqual(self.mg.auth, ('api','api-key'))
        expect = 'https://mailgun.example.com/lists/info@kghp.mailgun.org'
        self.assertEqual(self.mg.url(('lists', 'info@kghp.mailgun.org')), expect)

    def test_get(self, get, post, put, delete):
        params = {'address': 'info@kghp.mailgun.org'}
        url = 'https://mailgun.example.com/lists'
        self.mg.get(url, params=params)
        self.assert_called(get, url, params=params)

    def test_post(self, get, post, put, delete):
        data = {'to': ['kghp','altaurog'], 'from':'info', 'text':'hello'}
        url = 'https://mailgun.example.com/domain.example.com/messages'
        self.mg.post(url, data=data)
        self.assert_called(post, url, data=data)

    def test_send_message(self, get, post, put, delete):
        sender = 'info@kghp.com'
        recipients = ['info@example.com', 'chaver@example.com']
        subject = 'Test message'
        text = 'Body of message'
        self.mg.send_message(from_address=sender,
                            to=recipients,
                            subject=subject,
                            text=text)
        url = 'https://mailgun.example.com/domain.example.com/messages'
        data = {'from':sender, 'to':recipients, 'subject':subject, 'text':text}
        data['o:tracking'] = False
        self.assert_called(post, url, data=data)

        self.mg.send_message(from_address=sender,
                            to=recipients,
                            subject=subject,
                            text=text,
                            tracking=True)
        data['o:tracking'] = True
        self.assert_called(post, url, data=data)

        self.mg.send_message(from_address=sender,
                            to=recipients,
                            text=text)
        data['o:tracking'] = False
        del data['subject']
        self.assert_called(post, url, data=data)

    def test_new_list(self, get, post, put, delete):
        list_address = 'confirm@kghp.mailgun.org'
        name = 'Address Confirmation'
        description = 'For confirming address information by e-mail/web'
        url = 'https://mailgun.example.com/lists'
        data = {'address': list_address}
        self.mg.new_list(list_address)
        self.assert_called(post, url, data=data)

        self.mg.new_list(list_address, name=name)
        data['name'] = name
        self.assert_called(post, url, data=data)

        self.mg.new_list(list_address, name, description)
        data['description'] = description
        self.assert_called(post, url, data=data)

        self.mg.new_list(list_address, access_level='members')
        data = {'address': list_address, 'access_level': 'members'}
        self.assert_called(post, url, data=data)

    def test_get_lists(self, get, post, put, delete):
        self.mg.lists()
        url = 'https://mailgun.example.com/lists'
        self.assert_called(get, url, params={})

        data = {'items': [{
                     'address': 'confirm@kghp.mailgun.org',
                     'created_at': 'Fri, 19 Jul 2013 11:53:35 GMT',
                     'description': '',
                     'members_count': 0,
                     'name': ''
                    }
                ]}
        get.return_value.json.return_value = data
        lists = self.mg.lists(skip=40, limit=20)
        self.assert_called(get, url, params={'skip': 40, 'limit': 20})
        self.assertEqual(len(lists), 1)
        self.assertTrue(isinstance(lists[0], mailgun.MailingList))

    def test_get_list(self, get, post, put, delete):
        # from parent
        self.mg.get_list('confirm@kghp.mailgun.org')
        url = 'https://mailgun.example.com/lists/confirm@kghp.mailgun.org'
        self.assert_called(get, url)

        data = {'list': {
                     'address': 'confirm@kghp.mailgun.org',
                     'created_at': 'Fri, 19 Jul 2013 11:53:35 GMT',
                     'description': '',
                     'members_count': 20,
                     'name': ''
                }}

        with patch.object(self.mg, 'get', return_value=data) as mg_get:
            mlist = self.mg.get_list('confirm@kghp.mailgun.org')
            self.assertTrue(isinstance(mlist, mailgun.MailingList))

            # from child
            mlist = mailgun.MailingList(self.mg, {'address': 'xxx@example.com'})
            mlist.get()
            url = 'https://mailgun.example.com/lists/xxx@example.com'
            mg_get.assert_called_with(url)
            self.assertEqual(mlist.name, data['list']['name'])
            self.assertEqual(mlist.address, data['list']['address'])
            self.assertEqual(mlist.description, data['list']['description'])
            self.assertEqual(mlist.members_count, data['list']['members_count'])

    def test_ser_list(self, get, post, put, delete):
        data = {
                 'address': 'abc@kghp.example.com',
                 'created_at': 'Fri, 19 Jul 2013 11:53:35 GMT',
                 'description': 'Here is the list description',
                 'members_count': 20,
                 'name': 'Original Name',
               }
        mlist = mailgun.MailingList(self.mg, data)
        del data['created_at']
        del data['members_count']
        data['access_level'] = 'readonly'
        self.assertEqual(sorted(mlist.ser().items()), sorted(data.items()))

    def test_put_list(self, get, post, put, delete):
        data = {
                 'address': 'abc@kghp.example.com',
                 'created_at': 'Fri, 19 Jul 2013 11:53:35 GMT',
                 'description': '',
                 'members_count': 20,
                 'name': '',
                 'access_level': 'members',
               }
        mlist = mailgun.MailingList(self.mg, data)
        mlist.put()
        url = 'https://mailgun.example.com/lists/abc@kghp.example.com'
        del data['created_at']
        del data['members_count']
        self.assert_called(put, url, data=data)

    def test_delete_list(self, get, post, put, delete):
        data = {'address': 'abc@kghp.example.com',}
        mlist = mailgun.MailingList(self.mg, data)
        mlist.delete()
        url = 'https://mailgun.example.com/lists/abc@kghp.example.com'
        self.assert_called(delete, url)

    def test_new_member(self, get, post, put, delete):
        data = {'address': 'abc@kghp.example.com'}
        mlist = mailgun.MailingList(self.mg, data)
        member = mlist.new_member('member@example.com')
        url = 'https://mailgun.example.com/lists/abc@kghp.example.com/members'
        data = {'address': 'member@example.com'}
        self.assert_called(post, url, data=data)
        self.assertTrue(isinstance(member, mailgun.MailingListMember))
        self.assertEqual(member._path[:3], ('lists', 'abc@kghp.example.com', 'members'))

        mlist.new_member('member@example.com', name='New Member')
        data['name'] = 'New Member'
        self.assert_called(post, url, data=data)

        data['subscribed'] = 'yes'
        mlist.new_member('member@example.com', name='New Member', subscribed=True)
        self.assert_called(post, url, data=data)

        mlist.new_member('member@example.com', name='New Member', subscribed='Yes')
        self.assert_called(post, url, data=data)

        mlist.new_member('member@example.com', name='New Member', subscribed=False)
        data['subscribed'] = 'no'
        self.assert_called(post, url, data=data)

        mlist.new_member('member@example.com', name='New Member', subscribed='no')
        self.assert_called(post, url, data=data)

        mlist.new_member('member@example.com', vars={'slug':'xabv8'})
        data = {'address': 'member@example.com', 'vars':'{"slug":"xabv8"}'}

        mlist.new_member('member@example.com', upsert=True)
        data = {'address': 'member@example.com', 'upsert':'yes'}

    def test_add_members(self, get, post, put, delete):
        list_data = {'address': 'abc@kghp.example.com'}
        data = [{'address':'alt@yu.edu'}, {'address':'mag@one.com'}]
        mailgun.MailingList(self.mg, list_data).add_members(data)
        url = 'https://mailgun.example.com/lists/abc@kghp.example.com/members.json'
        self.assert_called(post, url, data={'members':json.dumps(data)})

        mailgun.MailingList(self.mg, list_data).add_members(data, False)
        url = 'https://mailgun.example.com/lists/abc@kghp.example.com/members.json'
        self.assert_called(post, url, data={'members':json.dumps(data), 'subscribed':'no'})

    def test_get_members(self, get, post, put, delete):
        list_data = {'address': 'abc@kghp.example.com'}
        mlist = mailgun.MailingList(self.mg, list_data)
        data = {'items': [{
                        'address': 'rashbi@meiron.example.com',
                        'name': 'Shimon',
                        'subscribed': True,
                        'vars': {'hash': 'zohar'},
                    }
            ]}
        get.return_value.json.return_value = data
        members = mlist.members()
        url = 'https://mailgun.example.com/lists/abc@kghp.example.com/members'
        self.assert_called(get, url, params={})
        self.assertEqual(len(members), 1)
        self.assertTrue(isinstance(members[0], mailgun.MailingListMember))
        self.assertEqual(members[0].subscribed, True)
        self.assertEqual(members[0].address, 'rashbi@meiron.example.com')
        self.assertEqual(members[0].name, 'Shimon')
        self.assertEqual(members[0].vars, {'hash': 'zohar'})

    def test_get_members_params(self, get, post, put, delete):
        list_data = {'address': 'abc@kghp.example.com'}
        mlist = mailgun.MailingList(self.mg, list_data)
        mlist.members(limit=10, skip=120)
        url = 'https://mailgun.example.com/lists/abc@kghp.example.com/members'
        self.assert_called(get, url, params={'limit': 10, 'skip': 120})

        mlist.members(subscribed=False)
        self.assert_called(get, url, params={'subscribed': 'no'})

    def assert_called(self, mock, url, **kwargs):
        mock.assert_called_with(url, auth=self.mg.auth, **kwargs)

