# Some Hilo automation ideas

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

```
alias: Défi Hilo Ancrage AM
description: ""
trigger:
  - platform: time
    at: "1:00:00"
  - platform: state
    entity_id:
      - sensor.defi_hilo
    to: appreciation
    from: scheduled
condition:
  - condition: template
    value_template: "{{'am' in state_attr('sensor.defi_hilo','next_events')[0]['period'] }}"
  - condition: or
    conditions:
      - condition: state
        entity_id: sensor.defi_hilo
        state: appreciation
      - condition: state
        entity_id: sensor.defi_hilo
        state: scheduled
  - condition: time
    after: "00:55:00"
    before: "01:05:00"
action:
  - choose:
      - conditions:
          - condition: numeric_state
            entity_id: zone.home
            above: 0
        sequence:
          - service: climate.set_temperature
            data:
              temperature: 21
            target:
              entity_id:
                - climate.thermostat_cuisine
        alias: Présent
      - conditions:
          - condition: numeric_state
            entity_id: zone.home
            below: 1
        sequence:
          - service: climate.set_temperature
            data:
              temperature: 23
            target:
              entity_id:
                - climate.thermostat_cuisine
        alias: Absent
mode: single
```
## Défi Hilo Ancrage PM avec détection de présence

Des appareils ont été enlevés pour simplifier.

On trigger à 12h ou quand le sensor tourne à appreciation. Garantie le trigger.

On vérifie que la liste de défis le prochain est en PM.

Condition sur le sensor défi car pourrait être en train de switcher d'état à 1h pile.

Condition d'heure en cas de reboot pas rapport de HA pour par rouler 2 fois.

Choose selon qu'il y ait quelqu'un à la maison ou pas.
```
alias: Défi Hilo Ancrage PM
description: ""
trigger:
  - platform: time
    at: "12:00:00"
  - platform: state
    entity_id:
      - sensor.defi_hilo
    to: appreciation
    from: scheduled
condition:
  - condition: template
    value_template: "{{'pm' in state_attr('sensor.defi_hilo','next_events')[0]['period'] }}"
  - condition: or
    conditions:
      - condition: state
        entity_id: sensor.defi_hilo
        state: appreciation
      - condition: state
        entity_id: sensor.defi_hilo
        state: scheduled
  - condition: time
    after: "11:55:00"
    before: "12:05:00"
action:
  - choose:
      - conditions:
          - condition: numeric_state
            entity_id: zone.home
            above: 0
        sequence:
          - service: climate.set_temperature
            data:
              temperature: 21
            target:
              entity_id:
                - climate.thermostat_cuisine
        alias: Présent
      - conditions:
          - condition: numeric_state
            entity_id: zone.home
            below: 1
        sequence:
          - service: climate.set_temperature
            data:
              temperature: 23
            target:
              entity_id:
                - climate.thermostat_cuisine
        alias: Absent
mode: single

```

## Défi Hilo Préchauffe AM
Je coupe mon convectair dans la salle de bain parce qu'il me gosse.

Je coupe mon échangeur d'air pour garder ma chaleur en dedans.

Perso je laisse le contrôle à Hilo pour cette phase, mon préchauffage est déjà entamé.
```
alias: Défi Hilo Préchauffe AM
description: ""
trigger:
  - platform: state
    entity_id:
      - sensor.defi_hilo
    to: pre_heat
    from: appreciation
    enabled: true
  - platform: time
    at: "04:00:00"
condition:
  - condition: time
    before: "04:05:00"
    after: "03:55:00"
  - condition: or
    conditions:
      - condition: state
        entity_id: sensor.defi_hilo
        state: pre_heat
      - condition: state
        entity_id: sensor.defi_hilo
        state: reduction
action:
  - service: climate.set_temperature
    data:
      temperature: 15
    target:
      entity_id: climate.thermostat_salle_de_bain
  - service: switch.turn_off
    metadata: {}
    data: {}
    target:
      entity_id: switch.prise_echangeur_d_air
mode: single

```

## Défi Hilo Réduction AM

```
alias: Défi Hilo Réduction AM
description: ""
trigger:
  - platform: state
    entity_id:
      - sensor.defi_hilo
    to: reduction
    from: pre_heat
    enabled: true
  - platform: time
    at: "06:00:00"
condition:
  - condition: time
    before: "06:05:00"
    after: "05:55:00"
  - condition: or
    conditions:
      - condition: state
        entity_id: sensor.defi_hilo
        state: pre_heat
      - condition: state
        entity_id: sensor.defi_hilo
        state: reduction
action:
  - service: climate.set_temperature
    data:
      temperature: 15
    target:
      entity_id:
        - climate.thermostat_cuisine
  - service: switch.turn_off
    metadata: {}
    data: {}
    target:
      entity_id: switch.prise_echangeur_d_air
mode: single

```

## Défi Hilo Réduction PM
Petite passe passe ici, j'éteins l'échangeur d'air juste à 7h pour sortir les odeurs du souper pareille.

```
alias: Défi Hilo Réduction PM
description: ""
trigger:
  - platform: state
    entity_id:
      - sensor.defi_hilo
    to: reduction
    from: pre_heat
    enabled: true
    id: Sensor
  - platform: time
    at: "17:00:00"
    id: 5pm
  - platform: time
    at: "19:00:00"
    id: 7pm
condition:
  - condition: or
    conditions:
      - condition: state
        entity_id: sensor.defi_hilo
        state: pre_heat
      - condition: state
        entity_id: sensor.defi_hilo
        state: reduction
action:
  - choose:
      - conditions:
          - condition: trigger
            id:
              - Sensor
              - 5pm
          - condition: time
            before: "17:05:00"
            after: "16:55:00"
        sequence:
          - service: climate.set_temperature
            data:
              temperature: 15
            target:
              entity_id:
                - climate.thermostat_cuisine
        alias: Réduction
      - conditions:
          - condition: trigger
            id:
              - 7pm
        sequence:
          - service: switch.turn_off
            metadata: {}
            data: {}
            target:
              entity_id: switch.prise_echangeur_d_air
mode: single

```

## Défi Hilo Recovery AM avec détection de présence/dodo travail de nuit
Dépendant s'il y a quelque à la maison ou quelqu'un qui dort à la maison les actions changent.


```
alias: Défi Hilo Recovery AM
description: ""
trigger:
  - platform: state
    entity_id:
      - sensor.defi_hilo
    to: recovery
    from: reduction
  - platform: time
    at: "10:00:00"
condition:
  - condition: time
    before: "10:05:00"
    after: "09:55:00"
action:
  - choose:
      - conditions:
          - condition: or
            conditions:
              - condition: state
                entity_id: sensor.defi_hilo
                state: reduction
              - condition: state
                entity_id: sensor.defi_hilo
                state: recovery
          - condition: numeric_state
            entity_id: zone.home
            above: 0
        sequence:
          - if:
              - condition: state
                entity_id: input_boolean.REDACTED_dodo_de_jour
                state: "off"
            then:
              - service: climate.set_temperature
                data:
                  temperature: 21
                target:
                  entity_id:
                    - climate.thermostat_cuisine
              - service: switch.turn_on
                metadata: {}
                data: {}
                target:
                  entity_id: switch.prise_echangeur_d_air
            else:
              - service: climate.set_temperature
                data:
                  temperature: 18
                target:
                  entity_id:
                    - climate.thermostat_cuisine
              - service: switch.turn_on
                metadata: {}
                data: {}
                target:
                  entity_id: switch.prise_echangeur_d_air
              - service: climate.set_temperature
                data:
                  temperature: 20.5
                target:
                  entity_id: climate.thermostat_chambre_des_maitres
      - conditions:
          - condition: or
            conditions:
              - condition: state
                entity_id: sensor.defi_hilo
                state: reduction
              - condition: state
                entity_id: sensor.defi_hilo
                state: recovery
          - condition: numeric_state
            entity_id: zone.home
            below: 1
        sequence:
          - service: climate.set_temperature
            data:
              temperature: 18
            target:
              entity_id:
                - climate.thermostat_cuisine
          - service: switch.turn_on
            metadata: {}
            data: {}
            target:
              entity_id: switch.prise_echangeur_d_air
mode: single

```

## Défi Hilo Recovery PM

```
alias: Défi Hilo Recovery PM
description: ""
trigger:
  - platform: state
    entity_id:
      - sensor.defi_hilo
    to: recovery
    from: reduction
  - platform: time
    at: "21:00:00"
condition:
  - condition: time
    before: "21:05:00"
    after: "20:55:00"
  - condition: or
    conditions:
      - condition: state
        entity_id: sensor.defi_hilo
        state: reduction
      - condition: state
        entity_id: sensor.defi_hilo
        state: recovery
action:
  - service: climate.set_temperature
    data:
      temperature: 21
    target:
      entity_id:
        - climate.thermostat_cuisine
  - service: climate.set_temperature
    data:
      temperature: 20.5
    target:
      entity_id: climate.thermostat_chambre_des_maitres
  - service: switch.turn_on
    metadata: {}
    data: {}
    target:
      entity_id: switch.prise_echangeur_d_air
mode: single

```
