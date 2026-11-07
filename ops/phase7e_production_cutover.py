#!/usr/bin/env python3
"""One-time staged TownLIT production cutover runner; no secrets printed."""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path('/srv/townlit')
STATE = Path('/root/townlit-dp-release-7d/phase7e-cutover')
BASE = '524dbffb'
RELEASE = '8634404a'
CONTAINERS = ('townlit_backend','townlit_celery','townlit_celery_beat')
SERVICES = ('backend','celery','celery-beat')
STAGES = (
  ('01','0106_address_additional_encrypted'),
  ('02','0107_address_remove_legacy_additional'),
  ('03','0108_identity_private_fields_expand'),
  ('04','0109_identity_private_fields_cutover'),
  ('05','0110_user_privacy_wave_expand'),
  ('06','0111_user_privacy_wave_cutover'),
  ('07','0112_contact_protection_expand'),
  ('08','0113_contact_phone_encrypted_cutover'),
  ('09',None),
  ('10','0114_email_encrypted_only_cutover'),
)
stage = 'PRECHECK'
started_migrations = False
stopped_writers = False

def command(args, *, capture=False, cwd=ROOT):
    result = subprocess.run(args, cwd=str(cwd), check=True, text=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ''

def docker_inspect(name):
    return json.loads(command(['docker','inspect',name],capture=True))[0]

def image_id(name):
    return command(['docker','image','inspect','--format','{{.Id}}',name], capture=True)

def set_stage(name):
    global stage
    stage = name
    print('BEGIN_'+name,flush=True)

def run_image(image, *args, capture=False):
    docker_args = ['docker','run','--rm','--pull','never','--network',prod_network,
                   '--read-only','--tmpfs','/tmp:rw,nosuid,nodev,size=64m',
                   '--cpus','1','--memory','1g','--pids-limit','256',
                   '--security-opt','no-new-privileges','--cap-drop','ALL',
                   '--env-file',str(env_file)]
    for mount in approved_mounts:
        docker_args.extend(['--mount',mount])
    docker_args.extend(['--workdir','/app','--entrypoint','python',image,
                        'manage.py',*args])
    return command(docker_args, capture=capture)

def dump_mysql(password,database):
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    out=Path('/root/townlit-dp-backups')/('townlit_phase7e_frozen_'+stamp+'.sql.gz')
    tmp=out.with_suffix('.partial')
    if out.exists() or tmp.exists():
        raise RuntimeError('Backup path already occupied')
    sqlcmd=['docker','exec','-i','townlit_mysql','sh','-c',
      'IFS= read -r MYSQL_PWD || exit 96; export MYSQL_PWD; '
      'exec mysqldump -uroot --single-transaction --quick --routines '
      '--events --triggers --no-tablespaces --set-gtid-purged=OFF --databases "$1"',
      'sh',database]
    with open(tmp,'xb') as output:
        os.chmod(tmp,0o600)
        with subprocess.Popen(sqlcmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE) as proc:
            proc.stdin.write((password+'\n').encode('utf-8'))
            proc.stdin.close()
            with gzip.GzipFile(filename='',mode='wb',fileobj=output,compresslevel=6) as gz:
                while True:
                    data=proc.stdout.read(1024*1024)
                    if not data:break
                    gz.write(data)
            code=proc.wait()
            if code:
                raise RuntimeError('mysqldump failed; output redacted')
        output.flush();os.fsync(output.fileno())
    with gzip.open(tmp,'rb') as src:
        tables=sum(1 for line in src if line.startswith(b'CREATE TABLE '))
    if tables < 400:
        raise RuntimeError('Backup table count too small')
    tmp.rename(out)
    sha=hashlib.sha256()
    with open(out,'rb') as file:
        for block in iter(lambda:file.read(1024*1024),b''):
            sha.update(block)
    print('FROZEN_BACKUP_VERIFIED=YES',flush=True)
    print('FROZEN_TABLE_DEFINITIONS='+str(tables),flush=True)
    print('FROZEN_BACKUP_PATH='+str(out),flush=True)
    print('FROZEN_BACKUP_SHA256='+sha.hexdigest(),flush=True)
    return out

try:
    os.umask(0o077)
    if os.geteuid()!=0: raise RuntimeError('Run using sudo')
    if STATE.exists(): raise RuntimeError('Existing cutover state; do not rerun')
    if command(['git','-C',str(ROOT),'rev-parse','--short','HEAD'],capture=True)!=BASE:
        raise RuntimeError('Production Git revision changed')
    if command(['git','-C',str(ROOT),'rev-parse','--short','origin/release/data-protection-staged-rehearsal'],capture=True)!=RELEASE:
        raise RuntimeError('Release ref changed')
    command(['git','-C',str(ROOT),'diff','--quiet'])
    command(['git','-C',str(ROOT),'diff','--cached','--quiet'])
    for name in ('Dockerfile','docker-compose.yml','.dockerignore','entrypoint_backend.sh','entrypoint_worker.sh'):
        command(['git','-C',str(ROOT),'check-ignore','-q',name])
    for s in SERVICES:
        image_id('townlit-dp-'+s+':phase7d-'+RELEASE)
    for s,_ in STAGES:
        image_id('townlit-dp-migrate:stage'+s+'-'+RELEASE)

    config=json.loads(command(['docker','compose','--env-file','.env.production','config','--format','json'],capture=True))
    dbvars=config['services']['mysql']['environment']
    bevars=config['services']['backend']['environment']
    dbname=dbvars['MYSQL_DATABASE'];rootpw=dbvars['MYSQL_ROOT_PASSWORD']
    if not rootpw or not dbname or '\n' in rootpw or '\r' in rootpw:
        raise RuntimeError('Database config missing')
    if bevars.get('DATABASE_NAME')!=dbname or bevars.get('DATABASE_ENGINE','django.db.backends.mysql')!='django.db.backends.mysql':
        raise RuntimeError('Database target mismatch')
    if bevars.get('DATABASE_HOST','mysql') not in ('mysql','townlit_mysql'):
        raise RuntimeError('Unexpected database hostname')
    dpnames=['TOWNLIT_DP_FERNET_KEYS_JSON','TOWNLIT_DP_ACTIVE_KEY_ID',
             'TOWNLIT_DP_BLIND_INDEX_KEYS_JSON','TOWNLIT_DP_BLIND_INDEX_ACTIVE_KEY_ID']
    for s in SERVICES:
        other=config['services'][s]['environment']
        if any(other.get(k)!=bevars.get(k) for k in dpnames):
            raise RuntimeError('Service keyrings mismatch')
    for a,b in ((dpnames[0],dpnames[1]),(dpnames[2],dpnames[3])):
        ring=json.loads(bevars[a]); key=ring[bevars[b]]
        if len(base64.urlsafe_b64decode(key))!=32:
            raise RuntimeError('Invalid DP keyring')
    if not bevars.get('FERNET_KEY') or not bevars.get('MASTER_KEY'):
        raise RuntimeError('Missing legacy crypto key')
    nets=set(docker_inspect('townlit_mysql')['NetworkSettings']['Networks']) & set(docker_inspect('townlit_backend')['NetworkSettings']['Networks'])
    if len(nets)!=1: raise RuntimeError('Unexpected production network')
    prod_network=nets.pop()
    if prod_network in docker_inspect('townlit_dp_rehearsal_db')['NetworkSettings']['Networks']:
        raise RuntimeError('Rehearsal network overlaps with production')
    if not all(docker_inspect(c)['State']['Running'] for c in CONTAINERS):
        raise RuntimeError('Writers not running at preflight')
    if not Path('/root/townlit-dp-backups/townlit_phase7e_premaintenance_20261107_041952.sql.gz').is_file():
        raise RuntimeError('Verified online backup absent')
    approved_mounts=[]
    for m in docker_inspect('townlit_backend')['Mounts']:
        if m['Destination'] in ('/etc/cloudfront-keys','/run/secrets/townlit/apns/AuthKey_9LGH78S8ZQ.p8'):
            if m['Type']!='bind':raise RuntimeError('Unexpected secret mount')
            approved_mounts.append('type=bind,src='+m['Source']+',dst='+m['Destination']+',readonly')

    STATE.mkdir(mode=0o700,parents=True)
    env_file=STATE/'runner.env'
    bevars=dict(bevars)
    bevars.update(ENV_FILE='/dev/null',DJANGO_SETTINGS_MODULE='townlit_b.settings')
    with open(env_file,'x',encoding='utf-8') as f:
        for k,v in bevars.items():
            if v is None: v = ''
            if not isinstance(v,str) or '\n' in v or '\r' in v or '\x00' in v:
                raise RuntimeError('Invalid docker env encoding')
            f.write(k+'='+v+'\n')
    os.chmod(env_file,0o600)
    (STATE/'production-network.txt').write_text(prod_network+'\n')

    overlay=STATE/'docker-compose.dp-release.yml'
    overlay.write_text('services:\n'+''.join(
      '  '+s+':\n    image: townlit-dp-'+s+':phase7d-'+RELEASE+'\n' for s in SERVICES))
    prodcompose=['docker','compose','--env-file','.env.production',
       '-f','docker-compose.yml','-f',str(overlay)]
    cc=json.loads(command(prodcompose+['config','--format','json'],capture=True))
    for s in SERVICES:
        if cc['services'][s].get('image') != 'townlit-dp-'+s+':phase7d-'+RELEASE:
            raise RuntimeError('Compose release image mismatch')
    preflight_code = (
        'from django.db import connection;'
        'from django.db.migrations.recorder import MigrationRecorder;'
        'connection.ensure_connection();'
        'assert connection.settings_dict["NAME"] == ' + repr(dbname) + ';'
        'applied=MigrationRecorder(connection).applied_migrations();'
        'assert ("accounts","0105_user_auth_session_state") in applied;'
        'assert not any(a=="accounts" and "0106"<=n[:4]<="0114" for a,n in applied);'
        'print("PRODUCTION_BASELINE_DB_VERIFIED=YES")'
    )
    run_image('townlit-dp-migrate:stage01-'+RELEASE,'shell','-c',preflight_code)
    print('CUTOVER_PRECHECK_PASSED=YES',flush=True)

    set_stage('STOP_WRITERS')
    command(['docker','update','--restart=no',*CONTAINERS])
    stopped_writers = True
    command(['docker','stop','--time','120','townlit_celery_beat','townlit_backend','townlit_celery'])
    if any(docker_inspect(c)['State']['Running'] for c in CONTAINERS):
        raise RuntimeError('Not all writers stopped')
    print('ALL_WRITERS_STOPPED=YES')

    set_stage('FROZEN_BACKUP')
    dump_mysql(rootpw,dbname)
    set_stage('BASELINE_COUNTS')
    baseline_image='townlit-dp-base-backend:pre7d-'+BASE
    code='from django.contrib.auth import get_user_model;from apps.accounts.models import IdentityVerification,IdentityGrant,IdentityAuditLog;import json;print("TOWNLIT_ROW_COUNTS="+json.dumps([get_user_model()._base_manager.count(),IdentityVerification._base_manager.count(),IdentityGrant._base_manager.count(),IdentityAuditLog._base_manager.count()]))'
    base_out=run_image(baseline_image,'shell','-c',code,capture=True)
    base_counts=json.loads(base_out.split('TOWNLIT_ROW_COUNTS=')[-1].splitlines()[0])
    print('BASELINE_ROW_COUNTS_VERIFIED=YES',flush=True)

    for number, migration in STAGES:
        set_stage('STAGE_'+number)
        img='townlit-dp-migrate:stage'+number+'-'+RELEASE
        if number == '02':
            run_image('townlit-dp-migrate:stage01-'+RELEASE,'backfill_address_additional_encrypted','--verify-only')
        if number == '04':
            run_image('townlit-dp-migrate:stage03-'+RELEASE,'backfill_identity_private_fields','--verify-only')
        if number == '06':
            run_image('townlit-dp-migrate:stage05-'+RELEASE,'backfill_user_privacy_wave','--verify-only')
        if number == '08':
            run_image('townlit-dp-migrate:stage07-'+RELEASE,'backfill_contact_protection','--verify-only')
        if number == '10':
            run_image(img,'audit_email_cutover_dependencies','--strict','--limit','0')
            run_image(img,'verify_email_cutover_readiness')
        if migration:
            started_migrations=True
            run_image(img,'migrate','accounts',migration,'--noinput')
        if number=='01':
            run_image(img,'backfill_address_additional_encrypted','--apply','--confirm-production-apply')
            run_image(img,'backfill_address_additional_encrypted','--verify-only')
        if number=='03':
            run_image(img,'backfill_identity_private_fields','--apply')
            run_image(img,'backfill_identity_private_fields','--verify-only')
        if number=='05':
            run_image(img,'backfill_user_privacy_wave','--apply')
            run_image(img,'backfill_user_privacy_wave','--verify-only')
        if number=='07':
            run_image(img,'backfill_contact_protection','--apply')
            run_image(img,'backfill_contact_protection','--verify-only')
        if number=='04': run_image(img,'verify_identity_private_fields')
        if number=='06': run_image(img,'verify_user_privacy_wave')
        if number=='08': run_image(img,'verify_contact_protection')
        if number in ('09','10'): run_image(img,'verify_email_cutover_readiness')
        run_image(img,'migrate','--check','--noinput')
        print('STAGE_OK='+number,flush=True)

    set_stage('FINAL_VALIDATION')
    final_img='townlit-dp-backend:phase7d-'+RELEASE
    for checker in ('verify_identity_private_fields','verify_user_privacy_wave',
                    'verify_contact_protection','verify_email_cutover_readiness'):
        run_image(final_img,checker)
    run_image(final_img,'migrate','--check','--noinput')
    run_image(final_img,'check')
    final_out=run_image(final_img,'shell','-c',code,capture=True)
    final_counts=json.loads(final_out.split('TOWNLIT_ROW_COUNTS=')[-1].splitlines()[0])
    if final_counts!=base_counts:
        raise RuntimeError('Identity/account row counts changed across cutover')
    print('FINAL_ROW_COUNTS_MATCH_BASELINE=YES',flush=True)

    set_stage('START_NEW_SERVICES')
    command(prodcompose+['up','-d','--no-deps','--no-build','--pull','never','--force-recreate',*SERVICES])
    for service,container in zip(SERVICES,CONTAINERS):
        d=docker_inspect(container)
        if not d['State']['Running'] or d['Image']!=image_id('townlit-dp-'+service+':phase7d-'+RELEASE):
            raise RuntimeError('New service not running expected image: '+service)
        if d['HostConfig']['RestartPolicy']['Name']!='always':
            raise RuntimeError('Restart policy not restored: '+service)
    print('THREE_PRODUCTION_SERVICES_UP=YES',flush=True)

    set_stage('BACKEND_HTTP_HEALTH')
    import time
    import urllib.request
    import urllib.error
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request('http://127.0.0.1:8000/', headers={'Host':'townlit.com'})
    ready = False
    for attempt in range(12):
        try:
            with opener.open(request, timeout=3) as response:
                code = response.status
        except urllib.error.HTTPError as exc:
            code = exc.code
        except Exception:
            code = 0
        if 200 <= code < 500:
            ready = True
            break
        time.sleep(2)
    if not ready:
        raise RuntimeError('New backend failed HTTP readiness')
    print('BACKEND_HTTP_RESPONDING=YES',flush=True)

    set_stage('ALIGN_PRODUCTION_GIT')
    command(['git','-C',str(ROOT),'switch','--detach',RELEASE])
    for name in ('Dockerfile','docker-compose.yml','.dockerignore','entrypoint_backend.sh','entrypoint_worker.sh'):
        command(['git','-C',str(ROOT),'check-ignore','-q',name])
    print('PRODUCTION_SOURCE_ALIGNED=YES',flush=True)
    env_file.unlink(missing_ok=True)
    print('PHASE7E_PRODUCTION_CUTOVER_COMPLETED=YES',flush=True)
except Exception as exc:
    print('CUTOVER_FAILED_AT='+stage,flush=True)
    print('FAILURE='+type(exc).__name__+': '+str(exc)[:200],flush=True)
    if started_migrations:
        print('CRITICAL: Do NOT restart old images against partially migrated schema.',flush=True)
    elif stopped_writers:
        print('Schema unchanged; old services may be restored after review.',flush=True)
    sys.exit(1)
