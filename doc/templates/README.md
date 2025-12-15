## Some template ideas


@FrancoLoco shared his templates:

```
template:
  - sensor:
      - name: "Défi Hilo en cours?"
        unique_id: defi_hilo_in_progress
        state: "{{ is_state('sensor.defi_hilo', 'appreciation') or is_state('sensor.defi_hilo', 'pre_heat') or is_state('sensor.defi_hilo', 'reduction') }}"

      - name: "Limite max defi"
        unique_id: defi_hilo_allowed_kwh
        unit_of_measurement: 'kWh'
        state: >
          {% if state_attr('sensor.defi_hilo', 'next_events') | length  > 0 %}
            {{state_attr('sensor.defi_hilo', 'next_events')[0]['allowed_kWh']}}
          {% else%}
            {{0}}
          {% endif %}

      - name: "Montant max defi"
        unique_id: defi_hilo_allowed_cash
        unit_of_measurement: '$'
        state: >
          {% if state_attr('sensor.defi_hilo', 'next_events') | length  > 0 %}
            {{ (state_attr('sensor.defi_hilo', 'next_events')[0]['allowed_kWh'] * 0.55) | round(2) }}
          {% else%}
            {{0}}
          {% endif %}

      - name: "kWh utilise defi"
        unique_id: defi_hilo_used_kwh
        unit_of_measurement: 'kWh'
        state: >
          {% if state_attr('sensor.defi_hilo', 'next_events') | length  > 0 %}
            {{ state_attr('sensor.defi_hilo', 'next_events')[0]['used_kWh']}}
          {% else%}
            {{0}}
          {% endif %}

      - name: "Montant utilise defi"
        unique_id: defi_hilo_used_cash
        unit_of_measurement: '$'
        state: >
          {% if state_attr('sensor.defi_hilo', 'next_events') | length  > 0 %}
            {{ (state_attr('sensor.defi_hilo', 'next_events')[0]['used_kWh'] * 0.55) | round(2) }}
          {% else%}
            {{0}}
          {% endif %}

      - name: "Montant restant defi"
        unique_id: defi_hilo_remaining_cash
        unit_of_measurement: '$'
        state: >
          {% if state_attr('sensor.defi_hilo', 'next_events') | length  > 0 %}
            {{(( state_attr('sensor.defi_hilo', 'next_events')[0]['allowed_kWh'] - state_attr('sensor.defi_hilo', 'next_events')[0]['used_kWh']) * 0.55) | round(2) }}
          {% else%}
            {{0}}
          {% endif %}

      - name: "Montant total predit defi"
        unique_id: defi_hilo_predicted_cash
        unit_of_measurement: '$'
        state: >
          {% if state_attr('sensor.defi_hilo', 'next_events') | length  > 0 %}
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
          {% else%}
            {{0}}
          {% endif %}

      - name: "Montant accumule estime defi"
        unique_id: defi_hilo_currentdefi_cash
        unit_of_measurement: '$'
        state: >
          {% if state_attr('sensor.defi_hilo', 'next_events') | length  > 0 %}
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
          {% else%}
            {{0}}
          {% endif %}

      - name: "Montant moyen defi"
        unique_id: defi_hilo_avg_cash
        unit_of_measurement: '$'
        state: >
          {% if state_attr('sensor.recompenses_hilo', 'history') | count > 0 %}
            {% set recompense = states('sensor.recompenses_hilo') | float %}
            {% set nbdefis = states('sensor.defi_hilo_nb_defi_completes') | float %}
            {% if nbdefis > 0 %}
              {% set moyenne = (recompense / nbdefis) | round(2) %}
              {{"%.2f" | format(moyenne)}}
            {% else %}
              {{0}}
            {% endif %}
          {% else %}
            {{0}}
          {% endif %}

      - name: "Defi Hilo prochain moment"
        unique_id: defi_hilo_date_heure_next
        state: >
          {% if state_attr('sensor.defi_hilo', 'next_events') | length  > 0 %}
            {{as_timestamp((state_attr('sensor.defi_hilo','next_events')[0]['phases']['reduction_start']))|timestamp_custom("%A %Y-%m-%d %H:%M")  }}
          {% else%}
            {{'-'}}
          {% endif %}

      - name: "Defi Hilo moment le plus loin"
        unique_id: defi_hilo_date_heure_last
        state: >
          {% if state_attr('sensor.defi_hilo', 'next_events') | length  > 1 %}
            {{as_timestamp((state_attr('sensor.defi_hilo','next_events')[state_attr('sensor.defi_hilo', 'next_events') | length -1]['phases']['reduction_start']))|timestamp_custom("%A %Y-%m-%d %H:%M")  }}
          {% else%}
            {{'-'}}
          {% endif %}

      - name: "Nb de defis Hilo planifies"
        unique_id: defi_hilo_nb_defi_planifies
        state: >
          {% if state_attr('sensor.defi_hilo', 'next_events') | length  > 0 %}
            {{state_attr('sensor.defi_hilo', 'next_events') | length }}
          {% else%}
            {{'0'}}
          {% endif %}

      - name: "Nb de defis Hilo completes saison actuelle"
        unique_id: defi_hilo_nb_defi_completes
        state: >
          {% if state_attr('sensor.recompenses_hilo', 'history') | length  > 0 %}
            {{state_attr('sensor.recompenses_hilo', 'history')[0]['events'] | length}}
          {% else%}
            {{'0'}}
          {% endif %}

      - name: "Cout electricite aujourd'hui"
        unique_id: electricity_cost_today
        unit_of_measurement: 'CAD'
        state: >
          {% if state_attr('sensor.defi_hilo', 'next_events') | length  > 0 %}
            {{ "%.2f"|format(1.15*(float(states.sensor.hilo_energy_total_low.state, 0) *    float(states.sensor.hilo_rate_low.state, 0) +    float(states.sensor.hilo_energy_total_medium.state, 0) *   float(states.sensor.hilo_rate_medium.state, 0) + 0.435))  | round(2)}}
          {% else%}
            {{'0'}}
          {% endif %}

      - name: "kWh electricite aujourd'hui consomme"
        unique_id: electricity_kwh_today_consomme
        unit_of_measurement: 'kWh'
        state: >
          {% if state_attr('sensor.defi_hilo', 'next_events') | length  > 0 %}
            {{ float(states.sensor.hilo_energy_total_low.state, 0) +    float(states.sensor.hilo_energy_total_medium.state, 0) }}
          {% else%}
            {{'0'}}
          {% endif %}
```
