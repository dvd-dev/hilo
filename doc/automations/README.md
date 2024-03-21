# Some Hilo automation ideas

## Défi Hilo Ancrage AM avec détection de présence

Des appareils ont été enlevés pour simplifier.
On trigger à 1h du matin ou quand le sensor tourne à appreciation. Garantie le trigger.
On vérifie que la liste de défis le prochain est en AM
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