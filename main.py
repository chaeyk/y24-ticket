# -*- coding: utf-8 -*-
import configparser
import requests
from bs4 import BeautifulSoup
import webbrowser
from datetime import datetime, timedelta
import sys
import time
import argparse
from charset_normalizer import from_path
import re

def get_title(id):
    res = requests.get(f'http://ticket.yes24.com/Perf/{id}')
    res.raise_for_status()

    try:
        soup = BeautifulSoup(res.text, features='html.parser')

        # <html lang="ko">
        #  <head>
        #   <meta charset="UTF-8">
        #   <meta http-equiv="X-UA-Compatible" content="IE=edge">
        #   <meta name="viewport" content="width=device-width, initial-scale=1"/>
        #   <meta property="og:title" content="제 9회 김사월 쇼 : 사월을 기다리는 노래들" /><meta property="og:type" content="website" /><meta property="og:image" content="http://tkfile.yes24.com/upload2/PerfBlog/202203/20220330/20220330-41834.jpg" /><meta property="og:url" content="http://ticket.yes24.com/Perf/41834" /><meta property="og:site_name" content="YES24 티 켓" /><meta property="og:description" content="제 9회 김사월 쇼 : 사월을 기다리는 노래들 상세정보 장르: 콘서트 일시: 2022.04.23 ~ 2022.04.24 등급: 전체관람가 관람시간: 총 120분 장소: 서강대학교 메리홀 대극장 " /><meta property="fb:app_id" content="530899446925997" />
        #   <meta name="description" content="제 9회 김사월 쇼 : 사월을 기다리는 노래들 상세정보 장르: 콘서트 일시: 2022.04.23 ~ 2022.04.24 등급: 전체관람가 관람시간: 총 120분 장소: 서강대학교 메리홀 대극장 " />
        #   <!--#### Open Graph Meta ####-->
        #   <meta property="og:title" content="YES24 티켓"/>
        #   <meta property="og:description" content=""/>
        metas = soup('meta', attrs={'property': 'og:title'})
        for meta in metas:
            return meta['content']

        raise Exception('제목을 찾을 수 없다.')
    except Exception:
        # print(res.text)
        raise

# perfMonth: ex> 2022-05
def get_dts(id, perfMonth):
    print(f'id={id}, perfMonth={perfMonth}')
    res = requests.post(
        f'http://ticket.yes24.com/New/Perf/Sale/Ajax/axPerfDay.aspx',
        data=dict(
            pGetMode='days',
            pIdPerf=id,
            pPerfMonth=perfMonth,
            pIsMania=0,
        )
    )
    res.raise_for_status()

    dts = []
    try:
        # 2022-05-21,2022-05-22,
        tokens = res.text.split(',')
        for token in tokens:
            if token:
                dts.append(token.replace('-', ''))

        return dts
    except Exception:
        print(res.text)
        raise

def get_idTimes(id, dt):
    print(f'id={id}, dt={dt}')
    res = requests.post(
        f'http://ticket.yes24.com/NEw/Perf/Detail/Ajax/axPerfPlayTime.aspx',
        data=dict(
            Type='calendar',
            IdPerf=id,
            PlayDate=dt,
        )
    )
    res.raise_for_status()

    idTimes = []
    try:
        soup = BeautifulSoup(res.text, features='html.parser')

        # <a href='#' idTime='1167404' title='오후 6시 00분' onclick=jsf_pdi_ChangePlayTime('calendar','1167404','오후6시00분');><span>1회</span> 오후 6시 00분</a>
        links = soup('a')
        for link in links:
            idTimes.append((link['idtime'], link['title']))

        if not idTimes:
            raise Exception(f'공연 시간이 없다: {dt}')

        return idTimes
    except Exception:
        print(res.text)
        raise

def check_ticket(idTime):
    res = requests.post(
        f'http://ticket.yes24.com/NEw/Perf/Detail/Ajax/axPerfRemainSeat.aspx',
        data=dict(
            Type='calendar',
            IdTime=idTime,
            IdLock=0,
        )
    )
    res.raise_for_status()

    try:
        soup = BeautifulSoup(res.text, features='html.parser')

        # <dt>전석</dt><dd>77,000원<span>(잔여:92석)</span></dd>
        dds = soup('dd')
        for dd in dds:
            match = re.compile(r'잔여:(\d+)석').search(dd.text)
            if match:
                seats = int(match.group(1))
                return seats > 0

        return False
    except Exception:
        print(res.text)
        raise

def format_dt(dt):
    m = re.compile(r'(\d{4})(\d{2})(\d{2})').match(dt)
    return f'{m[1]}/{m[2]}/{m[3]}'

parser = argparse.ArgumentParser(description='HMG schedule poller.')
parser.add_argument('--config', '-c', dest='config', default='config.ini', help='specify config file.')
parser.add_argument('--section', '-s', dest='section', default='default', help='config section to read.')    

args = parser.parse_args()

config = configparser.ConfigParser()
config.read(args.config, encoding=from_path(args.config).best().first().encoding)

id = config.get(args.section, 'id')
perfMonths = re.split(' +', config.get(args.section, 'perfMonths'))
title = get_title(id)
notiurl = config.get(args.section, 'notiurl', fallback='')

print(f'-------------------------------------')
print(f'title={title}')
print(f'id={id}')
print(f'perfMonths={perfMonths}')
print(f'-------------------------------------')

while True:
    idTimes = []
    for perfMonth in perfMonths:
        dts = get_dts(id, perfMonth)
        for dt in dts:
            idTimes += get_idTimes(id, dt)

    for idTime in idTimes:
        if check_ticket(idTime[0]):
            message = f'{title} - {format_dt(dt)} {idTime[1]} 티켓 떴다!'
            print(f'bingo!! - {message}')
            webbrowser.open(f'http://ticket.yes24.com/Perf/{id}')
            if notiurl:
                requests.post(notiurl, json={'message': message})
            sys.exit()

    time.sleep(timedelta(minutes=1).total_seconds())
