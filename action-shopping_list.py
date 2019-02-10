#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from snipsTools import SnipsConfigParser
from hermes_python.hermes import Hermes
from hermes_python.ontology import *
import paho.mqtt.client as mqtt
import io
import requests

CONFIG_INI = "config.ini"

class ShoppingList(object):
    def __init__(self):
        # get the configuration
        try:
            self.config = SnipsConfigParser.read_configuration_file(CONFIG_INI)
        except :
            print 'Unable to load config'
            return

        # log in to the Bring API
        response = requests.get('https://api.getbring.com/rest/bringlists?email=' + self.config.get('secret').get('email') + '&password=' + self.config.get('secret').get('password'))
        if response.status_code == 200:
            self.UUID = response.json()['uuid'].encode('utf-8')
            self.publicUUID = response.json()['publicUuid'].encode('utf-8')
            self.bringListUUID = response.json()['bringListUUID'].encode('utf-8')
            print 'Login successfull'
        else:
            print 'Login failed'
            return

        self.headers = {
            'X-BRING-API-KEY': 'cof4Nc6D8saplXjE3h3HXqHH8m7VU2i1Gs0g85Sp',
            'X-BRING-CLIENT': 'android',
            'X-BRING-USER-UUID': self.UUID,
            'X-BRING-COUNTRY': 'FR'
        }

        # load the available shoppping lists
        self.shoppingLists = {}
        response = requests.get('https://api.getbring.com/rest/bringusers/' + self.UUID + '/lists', headers=self.headers)
        if response.status_code == 200:
            for lists in response.json()['lists']:
                self.shoppingLists[lists['name'].encode('utf-8')] = lists['listUuid'].encode('utf-8')
        else:
            print 'Unable to load shopping lists'
            return

        # load the available shopping lists to Snips to be sure they are up-to-date
        injecting_json = '{ "operations": [ [ "addFromVanilla", { "ShoppingListList" : ['
        first = 1
        for list in self.shoppingLists.keys():
            if first:
              first = 0
            else:
              injecting_json += ', '
            injecting_json += '"' + list + '"'
        injecting_json += '] } ] ] }'
        injecting_mqtt = mqtt.Client()
        injecting_mqtt.connect(self.config.get('global').get('mqtt-host'), int(self.config.get('global').get('mqtt-port')))
        injecting_mqtt.loop_start()
        rc = injecting_mqtt.publish('hermes/injection/perform', injecting_json)
        rc.wait_for_publish()
        if rc.is_published:
            print 'Injected the lists to Snips ASR and NLU'
        else:
            print 'Could not inject the lists to Snips ASR and NLU'
        injecting_mqtt.disconnect()

        # start listening to MQTT
        self.start_blocking()

    # --> Sub callback function, one per intent
    def intent_addItem_callback(self, hermes, intent_message):
        print 'Received intent: {}'.format(intent_message.intent.intent_name)
        hermes.publish_end_session(intent_message.session_id, "")

        if intent_message.slots:
            if intent_message.slots.list:
                listName = intent_message.slots.list.first().value.encode('utf-8')
            else:
                listName = self.config.get('secret').get('default-list')

            listUuid = self.shoppingLists[listName]

            itemList = ''
            for item in intent_message.slots.item.all():
                if item.value != 'unknownword':
                    payload = {
                        'purchase': item.value,
                        'uuid' : self.bringListUUID
                    }
                    response = requests.put('https://api.getbring.com/rest/bringlists/' + listUuid, data=payload, headers=self.headers)
                    if itemList == '':
                        itemList = item.value
                    else:
                        itemList = itemList+' et '+item.value

            message = "J'ai ajouté {} à la liste {}".format(itemList.encode('utf-8'), listName)
            print message
            hermes.publish_start_session_notification(intent_message.site_id, message.decode('utf-8'), "")
        else:
            print 'No slot found'
            hermes.publish_start_session_notification(intent_message.site_id, "Je n'ai pas compris, merci de réessayer".decode('utf-8'), "")

    # --> Master callback function, triggered everytime an intent is recognized
    def master_intent_callback(self,hermes, intent_message):
        coming_intent = intent_message.intent.intent_name
        if coming_intent == 'tnappez:addItemToShoppingList':
            self.intent_addItem_callback(hermes, intent_message)

    # --> Register callback function and start MQTT
    def start_blocking(self):
        MQTT_ADDR = "{}:{}".format(self.config.get('global').get('mqtt-host'), self.config.get('global').get('mqtt-port'))
        with Hermes(MQTT_ADDR) as h:
            h.subscribe_intents(self.master_intent_callback).start()

if __name__ == "__main__":
    ShoppingList()
