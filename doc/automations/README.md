# Quelques exemples d'automatisations

## Notification défis Hilo pendant le défi
Prérequis: sensors template de @Francoloco

Petite notification à part pour ma femme pour qu'elle sache quand elle peut recommencer à vivre.
```
alias: Défi Hilo Notification En Cours
description: ""
trigger:
  - platform: state
    entity_id:
      - sensor.defi_hilo
    from: scheduled
    to: appreciation
    id: appreciation
  - platform: state
    entity_id:
      - sensor.defi_hilo
    from: appreciation
    to: pre_heat
    id: pre_heat
  - platform: state
    entity_id:
      - sensor.defi_hilo
    from: pre_heat
    to: reduction
    id: reduction
  - platform: state
    entity_id:
      - sensor.defi_hilo
    from: reduction
    to: recovery
    id: recovery
  - platform: state
    entity_id:
      - sensor.defi_hilo
    from: recovery
    to: completed
    id: completed
condition:
  - condition: not
    conditions:
      - condition: state
        entity_id: sensor.defi_hilo
        state: scheduled
  - condition: template
    value_template: >
      {{ states('input_text.defi_hilo_last_state_notification') !=
      states('sensor.defi_hilo') }}
action:
  - choose:
      - conditions:
          - condition: trigger
            id:
              - appreciation
              - pre_heat
              - completed
        sequence:
          - service: notify.mobile_app_REDACTED
            data:
              title: Défi Hilo
              message: Le sensor défi est passé à {{ states('sensor.defi_hilo') }}
          - service: input_text.set_value
            metadata: {}
            data:
              value: "{{states('sensor.defi_hilo')}}"
            target:
              entity_id: input_text.defi_hilo_last_state_notification
      - conditions:
          - condition: trigger
            id:
              - reduction
        sequence:
          - service: notify.mobile_app_REDACTED
            data:
              title: Défi Hilo
              message: >-
                Le sensor défi est passé à {{ states('sensor.defi_hilo') }}, le
                montant maximal possible est de
                {{states('sensor.defi_hilo_allowed_cash')}}$
          - service: input_text.set_value
            metadata: {}
            data:
              value: "{{states('sensor.defi_hilo')}}"
            target:
              entity_id: input_text.defi_hilo_last_state_notification
      - conditions:
          - condition: trigger
            id:
              - recovery
        sequence:
          - service: notify.mobile_app_iphone_ian
            data:
              title: Défi Hilo
              message: >-
                Le sensor défi est passé à {{states('sensor.defi_hilo')}}, le
                montant obtenu estimé est de
                {{states('sensor.defi_hilo_remaining_cash')}}$
          - service: notify.mobile_app_REDACTED
            data:
              title: Défi Hilo
              message: >-
                Le sensor défi est passé à {{ states('sensor.defi_hilo') }} plus
                besoin de faire attention
          - service: input_text.set_value
            metadata: {}
            data:
              value: "{{states('sensor.defi_hilo')}}"
            target:
              entity_id: input_text.defi_hilo_last_state_notification
mode: single

```

## Défi Hilo Ancrage AM avec détection de présence

Des appareils ont été enlevés pour simplifier.

On trigger à 1h du matin ou quand le sensor tourne à appreciation. Garantie le trigger.

On vérifie que la liste de défis le prochain est en AM.

Condition sur le sensor défi car pourrait être en train de switcher d'état à 1h pile.

Condition d'heure en cas de reboot pas rapport de HA pour par rouler 2 fois.

Choose selon qu'il y ait quelqu'un à la maison ou pas.


[YAML](https://github.com/dvd-dev/hilo/blob/main/doc/automations/Défi_Hilo_Ancrage_AM.yaml)


## Défi Hilo Ancrage PM avec détection de présence

Des appareils ont été enlevés pour simplifier.

On trigger à 12h ou quand le sensor tourne à appreciation. Garantie le trigger.

On vérifie que la liste de défis le prochain est en PM.

Condition sur le sensor défi car pourrait être en train de switcher d'état à 1h pile.

Condition d'heure en cas de reboot pas rapport de HA pour par rouler 2 fois.

Choose selon qu'il y ait quelqu'un à la maison ou pas.

[YAML](https://github.com/dvd-dev/hilo/blob/main/doc/automations/Défi_Hilo_Ancrage_PM.yaml)

## Défi Hilo Préchauffe AM
Je coupe mon convectair dans la salle de bain parce qu'il me gosse.

Je coupe mon échangeur d'air pour garder ma chaleur en dedans.

Perso je laisse le contrôle à Hilo pour cette phase, mon préchauffage est déjà entamé.


[YAML](https://github.com/dvd-dev/hilo/blob/main/doc/automations/Défi_Hilo_Préchauffe_AM.yaml)


## Défi Hilo Réduction AM

[YAML](https://github.com/dvd-dev/hilo/blob/main/doc/automations/Défi_Hilo_Réduction_AM.yaml)


## Défi Hilo Réduction PM
Petite passe passe ici, j'éteins l'échangeur d'air juste à 7h pour sortir les odeurs du souper pareille.

[YAML](https://github.com/dvd-dev/hilo/blob/main/doc/automations/Défi_Hilo_Réduction_PM.yaml)

## Défi Hilo Recovery AM avec détection de présence/dodo travail de nuit
Dépendant s'il y a quelque à la maison ou quelqu'un qui dort à la maison les actions changent.


[YAML](https://github.com/dvd-dev/hilo/blob/main/doc/automations/Défi_Hilo_Reprise_AM.yaml)


## Défi Hilo Recovery PM

[YAML](https://github.com/dvd-dev/hilo/blob/main/doc/automations/Défi_Hilo_Reprise_PM.yaml)

## Reset de la valeur energy lorsque les thermostats sont gérés via Z2M

La valeur `energy` maximale pour les thermostats Hilo HT402 est de `500`, et elle ne peut pas être réinitialisée manuellement car il est impossible d'écrire cet attribut directement. Cette valeur est automatiquement réinitialisée par le thermostat lui même chaque jour à minuit. Afin que cela fonctionne, il faut que l'heure soit correctement paramétrée sur les thermostats. Lorsqu'ils sont appairés à la passerelle Hilo, ce paramétrage est fait par un message broadcast de la passerelle comme celui-ci:

```
Frame 593: Packet, 55 bytes on wire (440 bits), 55 bytes captured (440 bits)
IEEE 802.15.4 Data, Src: 0x7eed, Dst: Broadcast
ZigBee Network Layer Data, Dst: Broadcast, Src: 0x0000
ZigBee Application Support Layer Data, Dst Endpt: 255, Src Endpt: 1
    Frame Control Field: Data (0x08)
    Destination Endpoint: 255
    Cluster: Time (0x000a)
    Profile: Home Automation (0x0104)
    Source Endpoint: 1
    Counter: 89
ZigBee Cluster Library Frame, Command: Report Attributes, Seq: 46
    Frame Control Field: Profile-wide (0x08)
    Sequence Number: 46
    Command: Report Attributes (0x0a)
    Attribute Field, Uint32: 821194320
        Attribute: Local Time (0x0007)
        Data Type: 32-Bit Unsigned Integer (0x23)
        Uint32: 821194320 (0x30f26e50)
```

Afin de répliquer ce comportement il est possible d'envoyer régulièrement (idéalement plusieurs fois un peu avant et après minuit) un message similaire à celui de la passerelle au topic `zigbee2mqtt/bridge/request/action`. Cela peut être fait avec un script comme celui-ci:
```yaml
action: mqtt.publish
metadata: {}
data:
  qos: "1"
  payload: >-
    {% set zigbee_epoch = (as_timestamp(now()) - as_timestamp('2000-01-01 00:00:00')) | int %}
        {
            "action": "raw",
            "params": {
                "network_address": 65532,
                "dst_endpoint": 255,
                "src_endpoint": 1,
                "profile_id": 260,
                "cluster_key": 10,
                "zcl": {
                    "frame_type": 0,
                    "direction": 1,
                    "disable_default_response": true,
                    "command_key": 10,
                    "payload": [
                        {
                            "attrId": 7,
                            "dataType": 35,
                            "attrData": {{ zigbee_epoch }}
                        }
                    ]
                }
            }
        }
  topic: zigbee2mqtt/bridge/request/action
  ```

  Ou en utilisant l'automation MqttPublishTimeThermostatsForReset.yaml de ce repository.
