import json
import os
import math

# metadata
metadata = {
    'protocolName': 'Station A SLP-005',
    'author': 'Chaz <protocols@opentrons.com>',
    'source': 'Custom Protocol Request',
    'apiLevel': '2.3'
}

NUM_SAMPLES = 8
SAMPLE_VOLUME = 200
TIP_TRACK = False
CTRL_SAMPLES = True
RACK_DEF = 'opentrons_24_tuberack_eppendorf_2ml_safelock_snapcap'
PK_ADD = True


def run(protocol):

    # load labware
    source_racks = [
        protocol.load_labware(RACK_DEF, slot, 'source tuberack ' + str(i+1))
        for i, slot in enumerate(['1', '4', '7', '10'])
    ]
    dest_plate = protocol.load_labware(
        'nest_96_wellplate_2ml_deep', '5', '96-deepwell sample plate')

    tips1k = [protocol.load_labware('opentrons_96_filtertiprack_1000ul', '3')]
    p1000 = protocol.load_instrument(
        'p1000_single_gen2', 'right', tip_racks=tips1k)

    if PK_ADD:
        t20 = [protocol.load_labware('opentrons_96_filtertiprack_20ul', '6')]
        m20 = protocol.load_instrument('p20_multi_gen2', 'left', tip_racks=t20)
        al_block = protocol.load_labware(
            'opentrons_96_aluminumblock_generic_pcr_strip_200ul', '2')
        pk = al_block['A1']
        num_cols = math.ceil(NUM_SAMPLES/8)
        dests_multi = dest_plate.rows()[0][:num_cols]

    # setup samples
    sources = [
        well for rack in source_racks for well in rack.wells()][:NUM_SAMPLES]
    dests_single = dest_plate.wells()[:NUM_SAMPLES]
    if CTRL_SAMPLES:
        controls = protocol.load_labware(
            'opentrons_24_aluminumblock_nest_1.5ml_snapcap', '11')
        sources = sources[:-2]
        sources.append(controls['A1'])  # positive control
        sources.append(controls['B1'])  # negative control

    tip_log = {'count': {}}
    folder_path = '/data/A'
    tip_file_path = folder_path + '/tip_log.json'
    if TIP_TRACK and not protocol.is_simulating():
        if os.path.isfile(tip_file_path):
            with open(tip_file_path) as json_file:
                data = json.load(json_file)
                if 'tips1000' in data:
                    tip_log['count'][p1000] = data['tips1000']
                else:
                    tip_log['count'][p1000] = 0
                if 'tips20' in data:
                    tip_log['count'][m20] = data['tips20']
                else:
                    tip_log['count'][m20] = 0
    else:
        tip_log['count'] = {p1000: 0, m20: 0}

    tip_log['tips'] = {
        p1000: [tip for rack in tips1k for tip in rack.wells()],
        m20: [tip for rack in t20 for tip in rack.rows()[0]]
    }
    tip_log['max'] = {
        pip: len(tip_log['tips'][pip])
        for pip in [p1000, m20]
    }

    def pick_up(pip):
        nonlocal tip_log
        if tip_log['count'][pip] == tip_log['max'][pip]:
            protocol.pause('Replace ' + str(pip.max_volume) + 'µl tipracks before \
resuming.')
            pip.reset_tipracks()
            tip_log['count'][pip] = 0
        pip.pick_up_tip(tip_log['tips'][pip][tip_log['count'][pip]])
        tip_log['count'][pip] += 1

    # transfer sample
    protocol.comment("Adding samples to destination plate...")
    for s, d in zip(sources, dests_single):
        pick_up(p1000)
        p1000.transfer(SAMPLE_VOLUME, s.bottom(5), d.bottom(5), air_gap=100,
                       new_tip='never')
        p1000.air_gap(100)
        p1000.drop_tip()

    # add PK if done in this step
    if PK_ADD:
        protocol.comment("Adding PK to samples...")
        for d in dests_multi:
            pick_up(m20)
            m20.transfer(20, pk, d, new_tip='never')
            m20.mix(5, 20, d)
            m20.blow_out()
            m20.drop_tip()

    protocol.comment("Protocol complete!")

    # track final used tip
    if TIP_TRACK and not protocol.is_simulating():
        if not os.path.isdir(folder_path):
            os.mkdir(folder_path)
        data = {
            'tips1000': tip_log['count'][p1000],
            'tips20': tip_log['count'][m20]
        }
        with open(tip_file_path, 'w') as outfile:
            json.dump(data, outfile)
