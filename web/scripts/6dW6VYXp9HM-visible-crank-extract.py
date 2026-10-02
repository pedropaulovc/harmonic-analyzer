#!/usr/bin/env python3
"""Shot-local visible main-crank measurements; images remain private.

Run: uv run --no-project --python web/.vite/calibration-venv/bin/python \
    web/scripts/6dW6VYXp9HM-visible-crank-extract.py
No bank phase, native handedness, camera, or home is inferred by this producer.

Packet API: linearly interpolate frames[].relativeCrankTurns only inside
interval.startSeconds..endSeconds. Positive means clockwise in ORIGINAL pixels.
Native crankTurns requires an explicitly chosen +/- sign and shot-local offset;
neither is measured. Preserve one fixed chosen-feasible20 phase/amplitude setup
as unobserved. Never join this zero to the separate112..119s bank shot.

The narrow source ellipse is an affine approximation, not camera calibration:
full windings/periods are observable; sub-turn phase and local speed are
approximate. Independent disjoint steel-pixel controls never enter the fit.
Native identity metadata is read from MECHANISM_DATA through Bun at execution.
Producer/native/kinematics hashes must stay unchanged until packet publication.
"""
from pathlib import Path
import hashlib
import json
import subprocess

import cv2
import numpy as np

WEB = Path(__file__).resolve().parents[1]
VIDEO = WEB / '.vite/reference-root/videos/6dW6VYXp9HM.mp4'
PRIVATE = WEB / '.vite/verification-output/6dW6VYXp9HM-visible-crank'
OUTPUT = WEB / 'content/6dW6VYXp9HM.visible-crank-motion.json'
EXPECTED_SHA = '5fc75341c088475bdcbad1764a8d99269f51bc287495063072a760a935319a52'
FIRST, LAST = 2392, 2598


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n')


def collar(image):
    # Brass collar between dark wood grip and steel arm. Skin, the shaft/hub,
    # and the arm are NOT tracked features. Fixed source-pixel search box.
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    patch = hsv[210:890, 570:628]
    mask = cv2.inRange(patch, np.array([14, 65, 95]), np.array([38, 245, 255]))
    _, _, stats, centres = cv2.connectedComponentsWithStats(mask)
    candidates = [(s[4], s, c) for s, c in zip(stats[1:], centres[1:])
                  if s[4] >= 50 and s[2] >= 5 and s[3] >= 5]
    if not candidates:
        return None
    area, s, c = max(candidates, key=lambda row: row[0])
    return {'pixels': (c + [570, 210]).tolist(), 'areaPx': int(area),
            'boundsPx': [int(s[0]+570), int(s[1]+210), int(s[2]), int(s[3])]}


def steel_control(image):
    """Independent distal steel silhouette; no collar or fitted phase input."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = ((gray[225:890, 632:671] > 35) &
            (hsv[225:890, 632:671, 1] < 65)).astype('uint8')
    _, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    candidates = []
    for k, s in enumerate(stats[1:], 1):
        if s[4] <= 100 or s[3] <= 90:
            continue
        ys, xs = np.where(labels == k)
        for side, y in [('upper', ys.min()), ('lower', ys.max())]:
            absolute_y = int(y + 225)
            if (side == 'upper' and absolute_y >= 450) or (side == 'lower' and absolute_y <= 680):
                continue
            edge_x = float(np.median(xs[np.abs(ys-y) <= 3])) + 632
            candidates.append((abs(absolute_y-560), {
                'pixels': [edge_x, absolute_y], 'side': side,
                'status': 'observed', 'role': 'CHECK-not-used-for-motion-or-ellipse-fit'}))
    return max(candidates, key=lambda c: c[0])[1] if candidates else {
        'pixels': None, 'status': 'unobservable',
        'reason': 'No isolated long neutral-metal silhouette away from shaft/hub; foreshortening, blur or segmentation failure.'}


def relative_motion(rows):
    points = np.array([row['fitFeature']['pixels'] for row in rows])
    # Moving exposures only. The long bottom hold must not dominate the conic.
    moving = np.array([row['frameIndex'] <= 2507 for row in rows])
    centre, diameters, degrees = cv2.fitEllipse(points[moving].astype(np.float32))
    angle = np.deg2rad(degrees)
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    radii = np.array(diameters)/2
    unit = (points-centre) @ rotation / radii
    phase = np.unwrap(np.arctan2(unit[:, 1], unit[:, 0]))
    turns = (phase-phase[0])/(2*np.pi)
    times = np.array([row['timeSeconds'] for row in rows])
    predicted = (np.column_stack([np.cos(phase), np.sin(phase)])*radii) @ rotation.T + centre
    # Independent, period-only oracle: rising y midpoint crossings on the
    # right side of the observed ellipse. No imposed frequency or monotonic fit.
    crossings = []
    for i in range(1, len(points)):
        if points[i-1, 1] < centre[1] <= points[i, 1] and points[i, 0] > centre[0]:
            weight = (centre[1]-points[i-1, 1])/(points[i, 1]-points[i-1, 1])
            crossings.append(float(times[i-1]+weight*(times[i]-times[i-1])))
    residuals = np.linalg.norm(predicted-points, axis=1)
    signed_areas = []
    for start, end in zip(crossings[:-1], crossings[1:]):
        polygon = points[(times >= start) & (times <= end)]
        signed_areas.append(float(np.sum(polygon[:, 0]*np.roll(polygon[:, 1], -1) -
                                         polygon[:, 1]*np.roll(polygon[:, 0], -1))/2))
    assert all(area > 0 for area in signed_areas), 'Source clockwise winding must be observed, never assumed'
    hold = turns[np.array([row['frameIndex'] >= 2512 for row in rows])]
    control_deltas = []
    for i, row in enumerate(rows):
        row['relativeCrankTurns'] = float(turns[i])
        lo, hi = max(0, i-4), min(len(rows)-1, i+4)
        row['localSpeedTurnsPerSecond'] = float((turns[hi]-turns[lo])/(times[hi]-times[lo]))
        row['ellipsePredictedPixels'] = predicted[i].tolist()
        control = row['independentSteelControl']
        if control['pixels'] is not None:
            # Distal silhouette is NOT the collar centre: finite arm width,
            # perspective and blur cause an expected endpoint offset.
            delta = float(control['pixels'][1]-predicted[i, 1])
            control['distalEdgeMinusPredictedCollarYPx'] = delta
            control_deltas.append(abs(delta))
    return {
        'projection': 'source-only-affine-circle-ellipse; approximation, not measured native camera or exact perspective angular calibration',
        'centrePixels': list(centre), 'diametersPixels': list(diameters), 'rotationDegrees': degrees,
        'fitFrameRangeInclusive': [FIRST, 2507], 'fitFeatureOnly': 'brass-handle-collar-colour-component',
        'sourcePixelSign': 'positive is clockwise in x-right/y-down original pixels',
        'totalRelativeTurns': float(turns[-1]), 'pixelRange': [points.min(0).tolist(), points.max(0).tolist()],
        'radialResidualPixels': {'median': float(np.median(residuals)), 'p95': float(np.percentile(residuals,95)), 'maximum': float(residuals.max())},
        'sameDirectionMidlineCrossingSeconds': crossings,
        'completeCyclePeriodsSeconds': np.diff(crossings).tolist(),
        'completeCycleSpeedsTurnsPerSecond': (1/np.diff(crossings)).tolist(),
        'originalPixelClockwiseSignedPolygonAreasPx2': signed_areas,
        'visibleBottomHold': {'firstFrameIndex': 2512, 'lastFrameIndex': LAST,
                              'relativeTurnRange': [float(hold.min()), float(hold.max())]},
        'steelControlCount': len(control_deltas), 'steelControlNullCount': len(rows)-len(control_deltas),
        'steelDistalEdgeVsPredictedCollarAbsoluteYPixels': {
            'median': float(np.median(control_deltas)), 'p95': float(np.percentile(control_deltas,95)), 'maximum': float(max(control_deltas))},
        'controlInterpretation': 'Independent automatically segmented steel distal-region contour follows the collar vertical sweep. Finite-width offsets, blur and segmentation outliers are reported, not mislabelled point reprojection errors or a passed metric calibration gate. No control enters conic or drive fit.',
        'uncertainty': 'Clockwise winding and cycle periods observable. Within-cycle turns/speed use an affine ellipse approximation; near-edge-on lateral radius is small, so centroid/blur errors amplify phase error. No calibrated confidence interval, exact perspective speed, or native sign claimed.',
    }


def main():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    lineage_paths = [Path(__file__), WEB/'src/mechanics-data.ts', WEB/'src/kinematics.ts']
    lineage_hashes = [sha(path) for path in lineage_paths]
    native = json.loads(subprocess.check_output([
        'bun', '--eval',
        'import {MECHANISM_DATA as d} from "./src/mechanics-data.ts";'
        'const r=d.renderFrames;'
        'const m=r.worldMatrices["harmonic-analyzer/drive-train/crank-handle-1"];'
        'console.log(JSON.stringify({nativePivotMm:r.crankPivotMm,nativeAxis:r.crankAxis,'
        'nativeHandleRestCentreMm:m.slice(12,15).map(v=>v*1000)}));'
    ], cwd=WEB))
    assert all(len(vector) == 3 and np.isfinite(vector).all() for vector in native.values())
    assert sha(VIDEO) == EXPECTED_SHA, 'Unexpected original source identity'
    probe = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_frames',
        '-show_entries', 'frame=pts,best_effort_timestamp_time', '-of', 'json', str(VIDEO)]))['frames']
    cap = cv2.VideoCapture(str(VIDEO))
    cap.set(cv2.CAP_PROP_POS_FRAMES, FIRST)
    rows = []
    previews = []
    for index in range(FIRST, LAST + 1):
        ok, image = cap.read()
        assert ok
        point = collar(image)
        assert int(probe[index]['pts']) == index*1001, 'Unexpected native frame/PTS lineage'
        row = {'frameIndex': index, 'timeSeconds': int(probe[index]['pts'])/30000,
               'sourceImage': {'sourceSha256': EXPECTED_SHA, 'sha256Bgr8': hashlib.sha256(image.tobytes()).hexdigest(),
                               'pts': int(probe[index]['pts']), 'format': 'bgr8', 'width': 1920, 'height': 1080},
               'fitFeature': point, 'independentSteelControl': steel_control(image),
               'screwControl': {'pixels': None, 'status': 'unmeasured-intermittently-visible',
                                'reason': 'No reliable independent screw-centre track; never replaced by predictions.'},
               'woodGripControl': {'pixels': None, 'status': 'occluded',
                                   'reason': 'Hand obscures grip; skin is not a rigid crank landmark.'}}
        rows.append(row)
        if index % 4 == 0:
            crop = image[210:890, 480:700].copy()
            if point:
                p = np.rint(np.array(point['pixels'])-[480,210]).astype(int)
                cv2.circle(crop, tuple(p), 6, (0,255,0), 2)
            cv2.putText(crop, str(index), (5,20), 0, .6, (0,255,0), 1)
            previews.append(cv2.resize(crop,(110,340)))
    cap.release()
    while len(previews)%12:
        previews.append(np.zeros_like(previews[0]))
    cv2.imwrite(str(PRIVATE/'track-contact.png'), np.vstack([np.hstack(previews[i:i+12]) for i in range(0,len(previews),12)]))
    save(PRIVATE/'measurements.json', rows)
    assert all(row['fitFeature'] is not None for row in rows), 'Do not interpolate unavailable FIT observations'
    motion = relative_motion(rows)
    packet = {
        'schemaVersion': 1, 'kind': 'shot-local-visible-main-crank-relative-motion',
        'source': {'videoId': '6dW6VYXp9HM', 'sha256': EXPECTED_SHA, 'width': 1920, 'height': 1080,
                   'fps': {'numerator': 30000, 'denominator': 1001}, 'ptsTimeBase': '1/30000',
                   'pixelCoordinates': 'original full-resolution x-right y-down; no mirror or crop transform',
                   'imageHashConvention': 'SHA256 of OpenCV-decoded contiguous original 1080x1920x3 uint8 BGR bytes',
                   'opencvVersion': cv2.__version__, 'rights': 'Numeric evidence only; source images and video remain private.'},
        'lineage': {'producerPath': 'web/scripts/'+Path(__file__).name, 'producerSha256': lineage_hashes[0],
                    'nativeGeometryPath': 'web/src/mechanics-data.ts', 'nativeGeometrySha256': lineage_hashes[1],
                    'nativeGeometryDerivation': 'Bun imports MECHANISM_DATA: renderFrames.crankPivotMm, renderFrames.crankAxis, and renderFrames.worldMatrices[crank-handle-1][12:15]*1000. No copied native coordinates.',
                    'verification': 'Producer/nativeGeometry/kinematics SHA256 checked before extraction and immediately before packet publication; changed inputs abort.',
                    'kinematicsPath': 'web/src/kinematics.ts', 'kinematicsSha256': lineage_hashes[2]},
        'interval': {'shotId': 'analysis-16', 'shotBoundsSeconds': [79.44603333333333,87.02026666666667],
                     'startSeconds': rows[0]['timeSeconds'], 'endSeconds': rows[-1]['timeSeconds'],
                     'firstFrameIndex': FIRST, 'lastFrameIndex': LAST, 'continuousNativeFrames': True,
                     'excluded': 'Shot boundary/dissolve margins outside this bounded interval; no extrapolation beyond last sample.'},
        'shaftIdentity': {
            'source': 'Hand turns long steel arm on shaft immediately left of cone large-end drive, with chain sprocket and green bearing. Upper/downward arm exposures are the same main crank, not a second lower paper/feed crank.',
            'nativePaths': ['harmonic-analyzer/drive-train/crankshaft-1','harmonic-analyzer/drive-train/crank-arm-1','harmonic-analyzer/drive-train/crank-handle-1'],
            **native,
            'correspondenceAuthority': 'Assembly identity and adjacent cone/chain topology; not a calibrated source/native projection.',
            'sourceStationOrder': 'left-to-right harmonic20..1; native station j=0..19 harmonic20-j, increasing Z pitch; pre93s unmirrored shot'},
        'authority': {
            'qualified': ['actual-source native-frame PTS and BGR hashes','2D collar trajectory with lateral component','clockwise image-plane winding','shot-local relative zero','observed complete-cycle periods','independent steel silhouette controls'],
            'approximate': ['within-cycle relativeCrankTurns from source-only affine ellipse','localSpeedTurnsPerSecond'],
            'unobservable': ['absolute shaft home','native +Z handedness mapping','all20 channel phases and amplitudes','source/native measured camera'],
            'nativeSignCandidates': [-1,1], 'selectedNativeSign': None, 'absoluteNativeHomeTurns': None,
            'phaseTransferToOtherShots': False, 'forbiddenPhaseTransferIntervalSeconds': [112.3122,119.085633],
            'sceneQualification': 'No source50/20/10/5 or full77..87 scene-calibration claim.'},
        'integration': {
            'timeDomain': 'original source seconds; closed sample domain only; outside returns null',
            'interpolation': 'piecewise linear between adjacent native-frame relativeCrankTurns; no extrapolation or across-cut bridge',
            'relativeZero': {'frameIndex': FIRST, 'timeSeconds': rows[0]['timeSeconds'], 'turns': 0, 'meaning': 'first observed exposure, not shaft home'},
            'nativeInputFormula': 'crankTurns = explicitChosenNativeSign * relativeCrankTurns + explicitChosenShotLocalOffsetTurns',
            'nativeSignRequirement': 'Caller must expose +/- selection as chosen/unobserved until independently measured; never promote to source authority.',
            'fixedSetupRequirement': 'Caller supplies one fixed20 amplitudes/phases vector from its existing chosen-feasible setup, explicitly unobserved. This packet supplies none and must not fabricate zero phases.',
            'physicalChannelAngleFormula': '(20-j)*pi/40*crankTurns + fixedPhaseRad[j], j=0..19',
            'separation': 'Drive evidence only; no manual camera workaround or time-varying per-channel pose substitution. Existing bank packet at112..119 remains separate.'},
        'measurement': motion, 'frames': rows}
    assert [sha(path) for path in lineage_paths] == lineage_hashes, 'Producer or native/kinematic inputs changed during extraction'
    save(OUTPUT, packet)
    print(json.dumps(motion))
    print(json.dumps({'frames':len(rows),'missing':[r['frameIndex'] for r in rows if r['fitFeature'] is None]}))


if __name__ == '__main__':
    main()
