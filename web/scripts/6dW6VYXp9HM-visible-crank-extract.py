#!/usr/bin/env python3
"""Private original-MP4 visible-crank pixel/motion receipt.

The default output and preview crops stay in private .vite verification storage.
--output may select another private verification path or external temporary file,
never published/canonical content. No native metadata or native code is consumed.
The filename-derived source-pixel-support directory follows --output; the default
uses a distinct source-pixels folder, never the original private capture folder.

Linearly interpolate frames[].relativeCrankTurns only inside the measured shot
interval. Positive means clockwise in ORIGINAL pixels; native shaft sign/home,
bank setup and source/native camera remain unobserved and have no authority here.

The narrow source ellipse is an affine approximation, not camera calibration:
full windings/periods are observable; sub-turn phase and local speed are
approximate. Independent disjoint steel-pixel controls never enter the fit.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

import cv2
import numpy as np

WEB = Path(__file__).resolve().parents[1]
VIDEO = WEB / '.vite/reference-root/videos/6dW6VYXp9HM.mp4'
PRIVATE = WEB / '.vite/verification-output/6dW6VYXp9HM-source-pixels'
OUTPUT = PRIVATE / 'source-pixel-receipt.json'
EXPECTED_SHA = '5fc75341c088475bdcbad1764a8d99269f51bc287495063072a760a935319a52'
FIRST, LAST = 2392, 2598


def private_output(path):
    output = Path(path).resolve()
    external_temp = not output.is_relative_to(WEB.resolve().parent) and any(
        output.is_relative_to(Path(temp).resolve()) for temp in ('/tmp', '/var/tmp'))
    private = WEB.resolve() / '.vite/verification-output'
    private_escape = not output.is_relative_to(private) and any(
        parent.name == 'verification-output' and parent.parent.name == '.vite'
        and parent.parent.parent.resolve() == WEB.resolve()
        for parent in Path(path).absolute().parents)
    if private_escape or output.is_relative_to((WEB / 'content').resolve()) or not (
            output.is_relative_to(private) or external_temp):
        raise ValueError('Source-pixel receipts require private .vite/verification-output or external temporary output; cannot write published content or canonical originals')
    return output


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, default=VIDEO)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        output = private_output(args.output)
        support = private_output(output.parent / f'{output.stem}-source-pixel-support')
    except ValueError as error:
        parser.error(str(error))
    if args.video.resolve().is_relative_to((WEB / 'content/v39-source').resolve()):
        parser.error('Original source-pixel extraction cannot consume current source namespace inputs')
    producer_hash = sha(Path(__file__))
    if sha(args.video) != EXPECTED_SHA:
        raise ValueError('Unexpected original source identity')
    support.mkdir(parents=True, exist_ok=True)
    probe = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_frames',
        '-show_entries', 'frame=pts,best_effort_timestamp_time', '-of', 'json', str(args.video)]))['frames']
    cap = cv2.VideoCapture(str(args.video))
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
    cv2.imwrite(str(support/'track-contact.png'), np.vstack([np.hstack(previews[i:i+12]) for i in range(0,len(previews),12)]))
    save(support/'measurements.json', {
        'kind': 'historical-source-pixel-measurements', 'historicalDiagnostic': True,
        'publishable': False, 'productionIntegrated': False,
        'geometryAuthority': None, 'authorityScope': 'original-source-pixels-only',
        'frames': rows})
    assert all(row['fitFeature'] is not None for row in rows), 'Do not interpolate unavailable FIT observations'
    motion = relative_motion(rows)
    packet = {
        'schemaVersion': 1, 'kind': 'historical-source-pixel-crank-motion-receipt',
        'historicalDiagnostic': True, 'publishable': False, 'productionIntegrated': False,
        'authorityScope': 'original-source-pixels-only', 'geometryAuthority': None,
        'source': {'videoId': '6dW6VYXp9HM', 'sha256': EXPECTED_SHA, 'width': 1920, 'height': 1080,
                   'fps': {'numerator': 30000, 'denominator': 1001}, 'ptsTimeBase': '1/30000',
                   'pixelCoordinates': 'original full-resolution x-right y-down; no mirror or crop transform',
                   'imageHashConvention': 'SHA256 of OpenCV-decoded contiguous original 1080x1920x3 uint8 BGR bytes',
                   'opencvVersion': cv2.__version__, 'rights': 'Numeric evidence only; source images and video remain private.'},
        'lineage': {'producerPath': 'web/scripts/'+Path(__file__).name, 'producerSha256': producer_hash,
                    'verification': 'Original MP4 SHA256 checked before extraction; producer and MP4 SHA256 checked immediately before writing the private receipt. No native geometry/kinematics read or executed.'},
        'interval': {'shotId': 'analysis-16', 'shotBoundsSeconds': [79.44603333333333,87.02026666666667],
                     'startSeconds': rows[0]['timeSeconds'], 'endSeconds': rows[-1]['timeSeconds'],
                     'firstFrameIndex': FIRST, 'lastFrameIndex': LAST, 'continuousNativeFrames': True,
                     'excluded': 'Shot boundary/dissolve margins outside this bounded interval; no extrapolation beyond last sample.'},
        'sourceFeatureIdentity': {
            'source': 'Hand turns the long steel arm immediately left of the cone/chain and green bearing; collar and independent distal steel contour are original-pixel features only.',
            'nativeCorrespondence': None,
            'correspondenceAuthority': 'Source pixels only; no native part/material identity or geometry approval inferred.'},
        'authority': {
            'qualified': ['actual-source native-frame PTS and BGR hashes','2D collar trajectory with lateral component','clockwise image-plane winding','shot-local relative zero','observed complete-cycle periods','independent steel silhouette controls'],
            'approximate': ['within-cycle relativeCrankTurns from source-only affine ellipse','localSpeedTurnsPerSecond'],
            'unobservable': ['absolute shaft home','native handedness mapping','all20 channel phases and amplitudes','source/native measured camera','native material/body correspondence'],
            'nativeSignCandidates': [-1,1], 'selectedNativeSign': None, 'absoluteNativeHomeTurns': None,
            'sourceNativeCamera': None, 'nativeGeometryApproved': False,
            'phaseTransferToOtherShots': False, 'forbiddenPhaseTransferIntervalSeconds': [112.3122,119.085633],
            'sceneQualification': 'No source50/20/10/5 or full77..87 scene-calibration claim.'},
        'integration': {
            'timeDomain': 'original source seconds; closed sample domain only; outside returns null',
            'interpolation': 'piecewise linear between adjacent native-frame relativeCrankTurns; no extrapolation or across-cut bridge',
            'relativeZero': {'frameIndex': FIRST, 'timeSeconds': rows[0]['timeSeconds'], 'turns': 0, 'meaning': 'first observed exposure, not shaft home'},
            'scope': 'Private source-pixel diagnostic only; no native input binding or production integration. Native sign, absolute home, setup and source/native camera require separate evidence.'},
        'measurement': motion, 'frames': rows}
    if sha(Path(__file__)) != producer_hash or sha(args.video) != EXPECTED_SHA:
        raise ValueError('Producer or original source changed during extraction')
    save(output, packet)
    print(json.dumps(motion))
    print(json.dumps({'output':str(output),'supportDirectory':str(support),
                      'frames':len(rows),'missing':[r['frameIndex'] for r in rows if r['fitFeature'] is None]}))


if __name__ == '__main__':
    main()
