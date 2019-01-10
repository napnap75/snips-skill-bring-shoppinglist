#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from snipsTools import SnipsConfigParser
from hermes_python.hermes import Hermes
from hermes_python.ontology import *
import io
import requests


import inspect

CONFIG_INI = "config.ini"

MQTT_IP_ADDR = "localhost"
MQTT_PORT = 1883
MQTT_ADDR = "{}:{}".format(MQTT_IP_ADDR, str(MQTT_PORT))

class ShoppingList(object):
    def __init__(self):
        # get the configuration if needed
        try:
            self.config = SnipsConfigParser.read_configuration_file(CONFIG_INI)
        except :
            self.config = None

        # log in to the Bring API
        response = requests.get('https://api.getbring.com/rest/bringlists?email=' + self.config.get('secret').get('email') + '&password=' + self.config.get('secret').get('password'))
        if response.status_code == 200:
            self.UUID = response.json()['uuid'].encode('utf-8')
            self.publicUUID = response.json()['publicUuid'].encode('utf-8')
            self.bringListUUID = response.json()['bringListUUID'].encode('utf-8')
            print '[ShoppingList] Login successfull'
        else:
            print '[ShoppingList] Login failed'
            return

        # start listening to MQTT
        self.start_blocking()

    # --> Sub callback function, one per intent
    def intent_addItem_callback(self, hermes, intent_message):
        print '[ShoppingList] Received intent: {}'.format(intent_message.intent.intent_name)
        headers = {
            'X-BRING-API-KEY': 'cof4Nc6D8saplXjE3h3HXqHH8m7VU2i1Gs0g85Sp',
            'X-BRING-CLIENT': 'android',
            'X-BRING-USER-UUID': self.UUID,
            'X-BRING-COUNTRY': 'FR'
        }
        if intent_message.slots:
            if intent_message.slots.list:
                listName = intent_message.slots.list.first().value
            else:
                listName = 'Maison'

            itemList = ''
            for item in intent_message.slots.item.all():
                payload = {
                    'purchase': item.value,
                    'uuid' : self.bringListUUID
                }
                response = requests.put('https://api.getbring.com/rest/bringlists/' + self.bringListUUID, data=payload, headers=headers)
                print '[ShoppingList] Added "{}" to the shopping list'.format(item.value.encode('utf-8'))
                if itemList == '':
                    itemList = item.value
                else:
                    itemList = itemList+' et '+item.value

            hermes.publish_end_session(intent_message.session_id, "J'ai ajouté {} à la liste {}".decode('utf-8').format(itemList, listName))
        else:
            print '[ShoppingList] No slot found'
            hermes.publish_end_session(intent_message.session_id, "Je n'ai pas compris, merci de réessayer".decode('utf-8'))

    # --> Master callback function, triggered everytime an intent is recognized
    def master_intent_callback(self,hermes, intent_message):
        coming_intent = intent_message.intent.intent_name
        if coming_intent == 'tnappez:addItem':
            self.intent_addItem_callback(hermes, intent_message)

    # --> Register callback function and start MQTT
    def start_blocking(self):
        with Hermes(MQTT_ADDR) as h:
            h.subscribe_intents(self.master_intent_callback).start()

if __name__ == "__main__":
    ShoppingList()
