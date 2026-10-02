#!/usr/bin/env python3
"""Produce source-timed Synthesis bank alternatives and distinct exposed crank drive.

uv run --python web/.vite/calibration-venv/bin/python --no-project \
  web/scripts/generate-8KmVDxkia_w-automatic-motion.py

The high20 explanatory tube is explicitly annotation evidence. Its extrema time
an unsigned crank-equivalent advance; physical gray-metal and genuine nearest
rod-joint exposures are independent controls. +/− bank sense stays unresolved.
No images/video/model assets, historical seals or other corpora are changed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.signal import find_peaks, savgol_filter

WEB = Path(__file__).resolve().parents[1]
EVIDENCE = WEB/'content/8KmVDxkia_w.automatic-motion-evidence.json'
DATA = WEB/'src/mechanics-data.ts'
KINEMATICS = WEB/'src/kinematics.ts'
MECHANICS = WEB/'src/mechanics.ts'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_time(row):
    return row['sourceImage']['frameIndex']*1001/24000


def summarize(values):
    values = np.abs(values)
    return {'median':float(np.median(values)), 'p95':float(np.percentile(values,95)),
            'max':float(np.max(values))}


def build_packet():
    evidence = json.loads(EVIDENCE.read_text())
    source = evidence['source']
    if source['videoId'] != '8KmVDxkia_w' or source['fps'] != {'numerator':24000,'denominator':1001}:
        raise ValueError('Synthesis native source identity/clock differs')
    for group in ('annotations','physicalMetalFIT','physicalMetalCHECK'):
        for row in evidence[group]:
            image = row['sourceImage']
            if image['sourceSha256'] != source['sha256'] or abs(source_time(row)-row['timeSeconds'])>1e-9:
                raise ValueError(f'{group}: source image/native frame clock differs')
    checks = {row['sourceImage']['frameIndex'] for row in evidence['physicalMetalCHECK']}
    fits = [row for row in evidence['annotations'] if row['role']=='fit']
    if any(row['sourceImage']['frameIndex'] in checks for row in fits):
        raise ValueError('Independent metal control exposure entered annotation objective')
    times = np.array([source_time(row) for row in fits])
    pixels = np.array([row['pixel'][1] for row in fits])
    if not np.all(np.diff(times)>0):
        raise ValueError('Source annotations must have unique increasing native exposures')
    text = DATA.read_text()
    data = json.loads(text.split('export const MECHANISM_DATA = ',1)[1].rsplit(' as const',1)[0])
    channel = data['channel']

    def rocker(theta):
        # Exact unchanged mechanics.ts261..278 released source-only closure.
        lobe = theta-channel['camHomeRad']
        cx = channel['camShaftMm'][0]-channel['eccentricityMm']*np.sin(lobe)
        cy = channel['camShaftMm'][1]+channel['eccentricityMm']*np.cos(lobe)
        ax, ay = cx-channel['pivotMm'][0], cy-channel['pivotMm'][1]
        distance = np.hypot(ax,ay)
        radius2 = sum(value*value for value in channel['rodPinMm'])
        a = (radius2-channel['rodLengthMm']**2+distance*distance)/(2*distance)
        h = np.sqrt(radius2-a*a)
        px, py = (a*ax+h*ay)/distance, (a*ay-h*ax)/distance
        angle = np.arctan2(py,px)-math.atan2(channel['rodPinMm'][1],channel['rodPinMm'][0])
        return (angle+np.pi)%(2*np.pi)-np.pi

    home = float(minimize_scalar(lambda theta:float(rocker(theta)),bounds=(-.3,.3),method='bounded').x)
    smooth = savgol_filter(pixels,11,2)
    lower = find_peaks(smooth,distance=42,prominence=100)[0]
    upper = find_peaks(-smooth,distance=42,prominence=100)[0]
    extremes = sorted([(int(i),'lower') for i in lower]+[(int(i),'upper') for i in upper])
    if not extremes or extremes[0][1] != 'lower':
        raise ValueError('Source first observed sweep is no longer upper-to-lower')
    if any(a[1]==b[1] for a,b in zip(extremes,extremes[1:])):
        raise ValueError('Observed high20 extrema do not alternate continuously')
    # Last upper is visible before the cut, although a complete following lower
    # would be needed for find_peaks' prominence. Retain only its actual minimum.
    if extremes[-1][1]=='lower':
        last_lower = extremes[-1][0]
        tail = int(last_lower+np.argmin(smooth[last_lower:]))
        if tail>last_lower+15 and tail<len(times)-3:
            extremes.append((tail,'upper'))
    start = evidence['interval']['startSeconds']
    end = evidence['interval']['endSeconds']
    source_extrema = [
        {'frameIndex':fits[index]['sourceImage']['frameIndex'],
         'timeSeconds':float(times[index]),'kind':kind,'unsignedPhaseRad':step*math.pi}
        for step,(index,kind) in enumerate(extremes,1)]
    lo,hi = np.percentile(pixels,[1,99])
    folded = np.arccos(np.clip((.5*(lo+hi)-pixels)/(.5*(hi-lo)),-1,1))
    # Native extrema establish the half-sweep branch BEFORE inversion. Unlike
    # independent acos or sign-of-noisy-derivative selection this cannot switch
    # a genuine full cycle between adjacent source exposures.
    extreme_times = np.array([start]+[row['timeSeconds'] for row in source_extrema])
    leg = np.searchsorted(extreme_times,times,side='right')-1
    observed_phase = leg*math.pi+np.where(leg%2==0,folded,math.pi-folded)
    phase = np.empty(len(times))
    leg_fits = []
    # Source annotation localization cannot observe angular speed exactly at a
    # rocker extremum. Fit one bounded smooth within-leg shape to FIT exposures,
    # not pixel-jitter plateaus (which would falsely freeze the crank). The
    # positive derivative is a declared single-sense continuation choice.
    for j in range(len(extreme_times)):
        select = leg==j
        if not select.any():
            continue
        t0 = extreme_times[j]
        if j+1<len(extreme_times):
            t1 = extreme_times[j+1]
            fraction = (times[select]-t0)/(t1-t0)
            basis = np.sin(math.pi*fraction)
            relative = observed_phase[select]-j*math.pi
            shape = float(np.clip(np.dot(relative-math.pi*fraction,basis)/np.dot(basis,basis),-.6,.6))
            phase[select] = j*math.pi+math.pi*fraction+shape*basis
            leg_fits.append({'halfSweep':j,'shapeRad':shape,'fitCount':int(select.sum())})
        else:
            # Last partial leg has only its measured endpoint and no next
            # extremum. Interpolate its observed advance without extrapolation.
            final = float(observed_phase[-1])
            phase[select] = j*math.pi+(final-j*math.pi)*(times[select]-t0)/(end-t0)
            leg_fits.append({'halfSweep':j,'shapeRad':None,'fitCount':int(select.sum()),
                             'scope':'endpoint-limited partial source sweep'})
    knot_times = np.concatenate(([start],times))
    unsigned_phase = np.concatenate(([0.],phase))
    if knot_times[-1] != end:
        raise ValueError('Final source annotation does not reach bounded interval')
    last_phase = float(unsigned_phase[-1])
    half_times = np.array([start]+[row['timeSeconds'] for row in source_extrema])
    speeds = 2/np.diff(half_times)
    dense_speeds = np.diff(unsigned_phase)*2/math.pi/np.diff(knot_times)
    if not np.all(dense_speeds>0):
        raise ValueError('Source branch continuation must advance without crank freezes or reversals')
    bank_candidates = []
    for direction in (1,-1):
        def angles_at(rows,k):
            tt=np.array([source_time(row) for row in rows])
            q=np.interp(tt,knot_times,unsigned_phase)
            return rocker(home+direction*q*k/20)
        # Only physical FIT controls choose each conditional screen-space gauge.
        metal_fit = evidence['physicalMetalFIT']
        metal_x = angles_at(metal_fit,20)
        metal_y = np.array([row['pixel'][1] for row in metal_fit])
        metal_gauge = np.linalg.solve(np.column_stack([np.ones(2),metal_x]),metal_y)
        metal_checks = evidence['physicalMetalCHECK']
        predicted = metal_gauge[0]+metal_gauge[1]*angles_at(metal_checks,20)
        errors = predicted-np.array([row['pixel'][1] for row in metal_checks])
        nearest = evidence['nearestJointSource']['rows']
        nearest_fit = [row for row in nearest if row['role']=='fit-pixel-gauge-only']
        nearest_x = angles_at(nearest_fit,1)
        nearest_y = np.array([row['observation']['pixel'][1] for row in nearest_fit])
        nearest_gauge = np.linalg.solve(np.column_stack([np.ones(2),nearest_x]),nearest_y)
        nearest_checks = [row for row in nearest if row['role']=='check']
        nearest_predicted = nearest_gauge[0]+nearest_gauge[1]*angles_at(nearest_checks,1)
        nearest_errors = nearest_predicted-np.array([row['observation']['pixel'][1] for row in nearest_checks])
        bank_candidates.append({'id':f'bank-direction-{direction:+d}',
            'directionBranch':direction,'directionAuthority':'unresolved-source-equivalent-physical-sense-choice',
            'staticPhasesRad':[home]*20,
            'requiredSetup':{'coneSwingRad':0.,'driveCrankOffsetTurns':0.},
            'hiddenInputPolicy':'Preserve complete old feasible baseline amplitudes/gearing/magnification/other setup honestly chosen and unobserved; never promote to source measurements.',
            'knots':[{'timeSeconds':float(t),'crankTurns':float(direction*q*2/math.pi)} for t,q in zip(knot_times,unsigned_phase)],
            'conditionalSourcePixelGauges':{'far20Metal':metal_gauge.tolist(),'nearest1Joint':nearest_gauge.tolist(),'meaning':'Source-only per-feature affine Y vs native rocker angle; NOT recovered camera or GPU/native-projection acceptance.'},
            'independentControls':{
                'far20Metal':{'fitExposures':[row['sourceImage']['frameIndex'] for row in metal_fit],
                    'checkCount':len(metal_checks),'absoluteResidualPx':summarize(errors),
                    'rows':[{'frameIndex':row['sourceImage']['frameIndex'],'observedPixel':row['pixel'],
                        'predictedYPx':float(p),'residualYPx':float(e),'uncertaintyPx':row['uncertaintyPx']}
                        for row,p,e in zip(metal_checks,predicted,errors)]},
                'nearest1PhysicalJoint':{'fitExposures':[row['sourceImage']['frameIndex'] for row in nearest_fit],
                    'checkCount':len(nearest_checks),'absoluteResidualPx':summarize(nearest_errors),
                    'rows':[{'frameIndex':row['sourceImage']['frameIndex'],'observedPixel':row['observation']['pixel'],
                        'predictedYPx':float(p),'residualYPx':float(e),'uncertaintyPx':row['observation']['uncertaintyPx']}
                        for row,p,e in zip(nearest_checks,nearest_predicted,nearest_errors)]}}})
    crank = evidence['lowerCrank']
    def crank_angles(rows):
        return np.array([math.atan2(row['armMidlinePixel'][1]-row['centrePixel'][1],
            row['armMidlinePixel'][0]-row['centrePixel'][0])+2*math.pi*row['cycleOffset'] for row in rows])
    crank_fit = [row for row in crank['observations'] if row['role']=='fit']
    crank_check = [row for row in crank['observations'] if row['role']=='check']
    crank_reference = source_time(crank_fit[0])
    tt = np.array([source_time(row)-crank_reference for row in crank_fit])
    slope,intercept = np.linalg.lstsq(np.column_stack([tt,np.ones(len(tt))]),crank_angles(crank_fit),rcond=None)[0]
    if slope<=0:
        raise ValueError('Observed source clockwise crank no longer has positive signed advance')
    held_tt = np.array([source_time(row)-crank_reference for row in crank_check])
    crank_errors = slope*held_tt+intercept-crank_angles(crank_check)
    return {'schemaVersion':1,'videoId':'8KmVDxkia_w','source':source,'model':evidence['model'],
        'generationDependencies':{str(path.relative_to(WEB.parent)):{'sha256':digest(path)}
            for path in (EVIDENCE,DATA,KINEMATICS,MECHANICS,Path(__file__))},
        'bankInterval':evidence['interval'],'bankCandidates':bank_candidates,
        'sourceMotionQuality':'rough-measured-source-timed-candidate; conditional pixel gauges do not qualify every individual6px localization bound',
        'bankMeasurement':{'unsignedCrankAdvanceTurns':float(last_phase*2/math.pi),
            'averageUnsignedCrankTurnsPerVideoSecond':float(last_phase*2/math.pi/(end-start)),
            'halfSweepUnsignedCrankTurnsPerVideoSecondRange':[float(min(speeds)),float(max(speeds))],
            'chosenWithinSweepCrankTurnsPerVideoSecondRange':[float(min(dense_speeds)),float(max(dense_speeds))],
            'withinSweepFits':leg_fits,
            'sourceHigh20Extrema':source_extrema,'annotationFITCount':len(fits),
            'allPhysicalCHECKExposuresExcludedFromAnnotationFIT':True,
            'cadenceRule':'Actually observed H20 upper/lower extrema establish cumulative half-sweep branch (2crank-equivalent turns each). Dense source annotation FIT Y chooses one bounded smooth within-sweep phase shape; positive angular derivative is declared single-sense continuation, not measured exact speed at unobservable extrema. Independent CHECK exposures never fit cadence. Final partial sweep is endpoint-limited. Linear interpolation of cumulative crankTurns between native-source keys; no modulo, wall-clock clock or manual control.',
            'phaseAssociation':'All20stations use native upper-extreme phase at f2541 as explicitly source-informed/chosen initial alignment; measured H20 temporal drive then feeds exact physical harmonics20..1. H1 independent physical controls diagnose this choice.'},
        'lowerCrank':{'intervalSeconds':[source_time(crank_fit[0]),source_time(crank_check[-1])],
            'binding':crank['binding'],'direction':1,'directionAuthority':crank['sourceView'],
            'crankTurnsPerVideoSecond':float(slope/(2*math.pi)),
            'referenceSeconds':crank_reference,'crankTurnsAtReferenceModuloOne':float(((intercept-math.pi/2)/(2*math.pi))%1),
            'integerHomeAuthority':'Unobserved full-turn integer gauge; only actual arm orientation modulo1turn is observed.',
            'independentControlCount':len(crank_check),'independentAngularResidualRad':summarize(crank_errors),
            'phaseMatchQualified':False,
            'phaseQuality':'rough source-ray/constant-rate fit only; independent max angular residual is reported, not hidden or promoted to close crank phase match',
            'fitCount':len(crank_fit),'phaseLaw':'crankTurns=crankTurnsAtReferenceModuloOne+(time-referenceSeconds)*crankTurnsPerVideoSecond; native released crank-arm home is screen-down in this CAD−Z source view.',
            'bankTransferPermitted':False},
        'limitations':evidence['limitations'],'acceptance':{
            'sourceTimedAutomaticCandidate':True,'signedBankDriveRecovered':False,
            'twentyHistoricalPhasesRecovered':False,'amplitudeSettingsRecovered':False,
            'nativeCameraGeometryOrGpuAccepted':False,'historicalWitnessesRewritten':False}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=WEB/'content/8KmVDxkia_w.automatic-motion.json')
    args=parser.parse_args()
    packet=build_packet()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(packet,indent=2)+'\n')
    print(json.dumps({'output':str(args.output),'bankMeasurement':packet['bankMeasurement'],
        'controls':[{ 'directionBranch':candidate['directionBranch'],
            **{key:value['absoluteResidualPx'] for key,value in candidate['independentControls'].items()}}
            for candidate in packet['bankCandidates']], 'lowerCrank':packet['lowerCrank']},indent=2))


if __name__=='__main__':main()
