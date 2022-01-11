## Some template ideas


@FrancoLoco shared his templates:

```
  defi_hilo_in_progress:
    friendly_name: Défi Hilo en cours?
    value_template: "{{ is_state('sensor.defi_hilo', 'appreciation') or is_state('sensor.defi_hilo', 'pre_heat') or is_state('sensor.defi_hilo', 'reduction') }}"

  defi_hilo_allowed_kwh:
    unit_of_measurement: 'kWh'
    friendly_name: Limit max defi
    value_template: "{{ state_attr('sensor.defi_hilo', 'next_events')[0]['allowed_kWh'] }}"

  defi_hilo_allowed_cash:
    friendly_name: Montant max defi
    unit_of_measurement: '$'
    value_template: "{{ (state_attr('sensor.defi_hilo', 'next_events')[0]['allowed_kWh'] * 0.55) | round(2) }}"

  defi_hilo_used_kwh:
    friendly_name: kWh utilise defi
    unit_of_measurement: 'kWh'
    value_template: "{{ state_attr('sensor.defi_hilo', 'next_events')[0]['used_kWh']}}"

  defi_hilo_used_cash:
    friendly_name: Montant utilise defi
    unit_of_measurement: '$'
    value_template: "{{ (state_attr('sensor.defi_hilo', 'next_events')[0]['used_kWh'] * 0.55) | round(2) }}"

  defi_hilo_remaining_cash:
    friendly_name: Montant restant defi
    unit_of_measurement: '$'
    value_template: "{{(( state_attr('sensor.defi_hilo', 'next_events')[0]['allowed_kWh'] - state_attr('sensor.defi_hilo', 'next_events')[0]['used_kWh']) * 0.55) | round(2) }}"

  defi_hilo_predicted_cash:
    friendly_name: Montant total predit defi
    unit_of_measurement: '$'
    value_template: >
       {% set debutdefi = as_timestamp(state_attr('sensor.defi_hilo', 'next_events')[0]['phases']['reduction_start']) %}
       {% set maintenant =  (now().timestamp()) %}
       {% set delta = ((maintenant - debutdefi)) // 60 | float %}
       {% if delta <= 0  %}
       {% set delta = 1 %}
       {%endif %}
       {% if delta >= 240  %}
       {% set delta = 240 %}
       {%endif %}
       {%set predicteduse = (1/(delta/ 240 )) * float(states('sensor.defi_hilo_used_kwh'),0) %}
       {{((float(states('sensor.defi_hilo_allowed_kwh'),0) - predicteduse) * 0.55)  | round(2) }}

  defi_hilo_currentdefi_cash:
    friendly_name: Montant accumule estime defi
    unit_of_measurement: '$'
    value_template: >
      {% set debutdefi = as_timestamp(state_attr('sensor.defi_hilo', 'next_events')[0]['phases']['reduction_start']) %}
      {% set maintenant =  (now().timestamp()) %}
      {% set delta = ((maintenant - debutdefi) // 60) +1 | int %}
      {% if delta <= 0  %}
      {% set delta = 1 %}
      {%endif %}
      {% if delta >= 240  %}
      {% set delta = 240 %}
      {%endif %}
      {{ (delta/ 240 * ((float(states('sensor.defi_hilo_allowed_kwh'),0) - ((1/(delta/ 240 ) * float(states('sensor.defi_hilo_used_kwh'),0)))) * 0.55))  | round(2) }}
```
