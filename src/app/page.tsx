'use strict';
'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Swal from 'sweetalert2';
import ExecutiveCharts from '@/components/ExecutiveCharts';

interface UserSession {
  username: string;
  fullName: string;
  station: string;
  homeStation: string;
  unit: string;
  role: string;
}

interface PendingItem {
  recordId: string;
  timestamp: string;
  actionBy: string;
  unitId: string;
  formType: string;
  sheetName: string;
  icon: string;
}

interface HqDashboardData {
  totals: {
    v43: number;
    service: number;
    v42: number;
    v20: number;
    arrests: number;
    accidents: number;
    deaths: number;
    injured: number;
  };
  stations: Array<{
    stationId: string;
    v43: number;
    service: number;
    v42: number;
    v20: number;
    arrests: number;
    accidents: number;
    dead: number;
    injured: number;
  }>;
}

const getExternalDashboardUrl = (userObj: UserSession | null, selectedDiv?: string) => {
  const baseUrl = 'https://hwpd-invest-dashboard.vercel.app/';
  if (!userObj) return baseUrl;

  // 1. Super Commander / HQ Admin (national level)
  if (userObj.role === 'Super_Commander' || userObj.role === 'HQ_Admin') {
    if (selectedDiv && selectedDiv !== 'all') {
      return `${baseUrl}?tab=overview&kk=${selectedDiv}`;
    }
    return `${baseUrl}?tab=overview`;
  }

  // 2. Division level (e.g. station is "50")
  if (userObj.role === 'Division_Admin' || userObj.role === 'Division_Commander') {
    const kk = userObj.station.charAt(0);
    return `${baseUrl}?tab=overview&kk=${kk}`;
  }

  // 3. Station level (e.g. station is "51")
  if (userObj.role === 'Station_Admin' || userObj.role === 'Unit_Staff') {
    const kk = userObj.station.charAt(0);
    const stl = userObj.station.charAt(1);
    return `${baseUrl}?tab=overview&kk=${kk}&stl=${stl}`;
  }

  return baseUrl;
};

export default function HomePage() {
  const [user, setUser] = useState<UserSession | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Navigation
  const [currentView, setCurrentView] = useState<'login' | 'staff-menu' | 'admin-dashboard' | 'hq-dashboard' | 'commander-dashboard' | 'super-commander-dashboard' | 'hq-admin-dashboard' | 'formDaily' | 'formCheckpoint' | 'formArrest' | 'formAccident' | 'formMission' | 'formMissionView' | 'formInventory' | 'formDocument' | 'formRoyalGuard' | 'formFuel' | 'formMyHistory' | 'formTools'>('login');
  const [dailySubTab, setDailySubTab] = useState<'tab1' | 'tab2'>('tab1');
  const [fuelSubTab, setFuelSubTab] = useState<'refuel' | 'oil'>('refuel');
  const [hqTab, setHqTab] = useState<'overview' | 'stations' | 'pending'>('overview');
  const [invSubTab, setInvSubTab] = useState<'my-assets' | 'repair'>('my-assets');
  const [toolSubView, setToolSubView] = useState<'dashboard' | 'auto-arrest'>('dashboard');
  const [selectedDivision, setSelectedDivision] = useState('all');

  // Login inputs
  const [loginUser, setLoginUser] = useState('');
  const [loginPass, setLoginPass] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [formLoading, setFormLoading] = useState(false);

  // Super Commander Dispatch Center States
  const [cmdTitle, setCmdTitle] = useState('');
  const [cmdPriority, setCmdPriority] = useState('ด่วนที่สุด');
  const [cmdTargetDiv, setCmdTargetDiv] = useState('all');
  const [cmdDetails, setCmdDetails] = useState('');
  const [radioChannel, setRadioChannel] = useState('ช่องวิทยุผ่านดาวเทียม (บก.ทล.)');
  const [radioMessage, setRadioMessage] = useState('');

  // --- FORM FIELDS ---
  
  // 1. Daily Form
  const [dr_reportDateTime, setDrReportDateTime] = useState('');
  const [dr_unitId, setDrUnitId] = useState('');
  const [dr_dutyOfficer, setDrDutyOfficer] = useState('');
  const [dr_dutyPhone, setDrDutyPhone] = useState('');
  const [dr_carNumber, setDrCarNumber] = useState('');
  const [dr_driverName, setDrDriverName] = useState('');
  const [dr_driverPhone, setDrDriverPhone] = useState('');
  const [dr_radioOpName, setDrRadioOpName] = useState('');
  const [dr_radioOpPhone, setDrRadioOpPhone] = useState('');
  const [dr_startTime, setDrStartTime] = useState('');
  const [dr_endTime, setDrEndTime] = useState('');

  // Daily Result Form
  const [res_v43, setResV43] = useState('0');
  const [res_service, setResVService] = useState('0');
  const [res_v42, setResV42] = useState('0');
  const [res_v20, setResV20] = useState('0');
  const [res_chargesText, setResChargesText] = useState('');
  const [res_notes, setResNotes] = useState('');

  // 2. Checkpoint Form
  const [chk_reportDateTime, setChkReportDateTime] = useState('');
  const [chk_unitId, setChkUnitId] = useState('');
  const [chk_dutyOfficer, setChkDutyOfficer] = useState('');
  const [chk_totalPersonnel, setChkTotalPersonnel] = useState('');
  const [chk_carNumber, setChkCarNumber] = useState('');
  const [chk_location, setChkLocation] = useState('');
  const [chk_locationOther, setChkLocationOther] = useState('');

  // 3. Arrest Form
  const [arr_reportDateTime, setArrReportDateTime] = useState('');
  const [arr_unitId, setArrUnitId] = useState('');
  const [arr_suspectCount, setArrSuspectCount] = useState('1');
  const [arr_suspectsText, setArrSuspectsText] = useState('');
  const [arr_offense, setArrOffense] = useState('');
  const [arr_circumstances, setArrCircumstances] = useState('');

  // 4. Accident Form
  const [acc_reportDateTime, setAccReportDateTime] = useState('');
  const [acc_unitId, setAccUnitId] = useState('');
  const [acc_route, setAccRoute] = useState('');
  const [acc_km, setAccKm] = useState('');
  const [acc_direction, setAccDirection] = useState('');
  const [acc_locDetails, setAccLocDetails] = useState('');
  const [acc_deadCount, setAccDeadCount] = useState('0');
  const [acc_injuredCount, setAccInjuredCount] = useState('0');
  const [acc_hospital, setAccHospital] = useState('');
  const [acc_mainVehicle, setAccMainVehicle] = useState('');
  const [acc_oppVehicle, setAccOppVehicle] = useState('');

  // 5. Mission Form
  const [mis_reportDateTime, setMisReportDateTime] = useState('');
  const [mis_startTime, setMisStartTime] = useState('');
  const [mis_endTime, setMisEndTime] = useState('');
  const [mis_units, setMisUnits] = useState<string[]>([]);
  const [mis_details, setMisDetails] = useState('');
  const [mis_location, setMisLocation] = useState('');

  // 6. Mission View
  const [view_startDate, setViewStartDate] = useState('');
  const [view_endDate, setViewEndDate] = useState('');
  const [view_unitName, setViewUnitName] = useState('');
  const [missionsList, setMissionsList] = useState<any[]>([]);

  // 7. Inventory & Repair Forms
  const [rep_reportDateTime, setRepReportDateTime] = useState('');
  const [rep_brokenItem, setRepBrokenItem] = useState('');
  const [rep_reporterName, setRepReporterName] = useState('');
  const [rep_issueDetail, setRepIssueDetail] = useState('');

  // 8. Document Form
  const [doc_reportDateTime, setDocReportDateTime] = useState('');
  const [doc_subject, setDocSubject] = useState('');
  const [doc_type, setDocType] = useState('บันทึกข้อความ');
  const [doc_senderName, setDocSenderName] = useState('');

  // 9. Royal Guard Form
  const [rg_dateTime, setRgDateTime] = useState('');
  const [rg_missionName, setRgMissionName] = useState('');
  const [rg_type, setRgType] = useState<'prep' | 'complete'>('prep');
  const [rg_commanders, setRgCommanders] = useState('');
  const [rg_carNumbers, setRgCarNumbers] = useState('');
  const [rg_targetCount, setRgTargetCount] = useState('1');
  const [rg_details, setRgDetails] = useState('');

  // 10. Fuel Form
  const [fuel_actionDateTime, setFuelActionDateTime] = useState('');
  const [fuel_actionPerson, setFuelActionPerson] = useState('');
  const [fuel_plateNumber, setFuelPlateNumber] = useState('');
  const [fuel_currentMileage, setFuelCurrentMileage] = useState('');
  const [fuel_type, setFuelType] = useState('');
  const [fuel_liters, setFuelLiters] = useState('');
  const [fuel_price, setFuelPrice] = useState('');
  const [fuel_receiptNumber, setFuelReceiptNumber] = useState('');

  // 11. My History
  const [historyItems, setHistoryItems] = useState<PendingItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // 12. Auto Arrest Form
  const [aa_date, setAaDate] = useState('');
  const [aa_location, setAaLocation] = useState('');
  const [aa_suspectName, setAaSuspectName] = useState('');
  const [aa_offense, setAaOffense] = useState('');
  const [aa_circumstances, setAaCircumstances] = useState('');

  // Admin Pending Queue & Dashboard states
  const [pendingItems, setPendingItems] = useState<PendingItem[]>([]);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [hqData, setHqData] = useState<HqDashboardData | null>(null);
  const [hqLoading, setHqLoading] = useState(false);
  const [stationConfig, setStationConfig] = useState<Record<string, { name: string; units: string[] }>>({});

  // Service units (dynamically resolved from config based on user station/role)
  const unitsInStation = React.useMemo(() => {
    if (!user) return [];
    
    const reqStationId = user.station;
    
    // 1. Exact match (e.g. '11', '51')
    if (stationConfig[reqStationId]) {
      return stationConfig[reqStationId].units;
    }
    
    // 2. Division level (e.g. '50') -> collect all units in that division
    if (reqStationId.endsWith('0') && reqStationId.length === 2) {
      const divPrefix = reqStationId[0];
      const units: string[] = [];
      Object.entries(stationConfig).forEach(([stId, stConf]) => {
        if (stId.startsWith(divPrefix)) {
          units.push(...stConf.units);
        }
      });
      if (units.length > 0) {
        return Array.from(new Set(units));
      }
    }
    
    // 3. National / Headquarters level (e.g. '00', 'HQ') -> collect all units in the country
    if (reqStationId === '00' || reqStationId === '0' || reqStationId.toUpperCase() === 'HQ') {
      const units: string[] = [];
      Object.values(stationConfig).forEach(stConf => {
        units.push(...stConf.units);
      });
      if (units.length > 0) {
        return Array.from(new Set(units));
      }
    }
    
    // 4. Default fallback if stationConfig is not loaded yet or station not found
    return ['สามเงา', 'แม่สอด', 'คลองขลุง', 'พรานกระต่าย', 'เมืองตาก', 'ฝอ.กก.5'];
  }, [user, stationConfig]);

  useEffect(() => {
    checkSession();
    fetch('/api/config/stations')
      .then(res => res.json())
      .then(res => {
        if (res.status === 'success') {
          setStationConfig(res.data);
        }
      })
      .catch(err => console.error('Failed to load station configs', err));
  }, []);

  useEffect(() => {
    if (currentView === 'super-commander-dashboard') {
      fetchHqDashboard(selectedDivision);
    }
  }, [selectedDivision, currentView]);

  const checkSession = async () => {
    try {
      const res = await fetch('/api/auth/me');
      const result = await res.json();
      if (res.ok && result.status === 'success') {
        setUser(result.user);
        routeUserDefault(result.user);
      } else {
        setCurrentView('login');
      }
    } catch (err) {
      setCurrentView('login');
    } finally {
      setLoading(false);
    }
  };

  const routeUserDefault = (userObj: UserSession) => {
    setDrUnitId(userObj.unit);
    setChkUnitId(userObj.unit);
    setArrUnitId(userObj.unit);
    setAccUnitId(userObj.unit);
    setViewUnitName(userObj.unit);
    setRepReporterName(userObj.fullName);
    setDocSenderName(userObj.fullName);
    setFuelActionPerson(userObj.fullName);

    // If Super_Commander (บก.ทล.), route directly to super-commander-dashboard view
    if (userObj.role === 'Super_Commander') {
      setCurrentView('super-commander-dashboard');
      fetchHqDashboard('all');
      return;
    }

    // Prefetch queue or dashboard stats in the background based on role
    if (userObj.role === 'Station_Admin' || userObj.role === 'Division_Admin') {
      fetchPendingQueue();
    }
    if (userObj.role === 'Division_Admin' || userObj.role === 'Division_Commander' || userObj.role === 'Super_Commander') {
      fetchHqDashboard();
    }

    // Always route to main menu (12 buttons) first
    setCurrentView('staff-menu');
  };

  const handleSendDirective = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormLoading(true);
    try {
      const data = {
        reportDateTime: new Date().toISOString(),
        startTime: new Date().toISOString(),
        endTime: new Date(Date.now() + 86400000).toISOString(),
        targetUnits: cmdTargetDiv === 'all' ? 'ทุกกองกำกับการ (กก.1 - กก.8)' : `กก.${cmdTargetDiv} บก.ทล.`,
        missionDetails: `[ข้อสั่งการผู้บังคับบัญชา - ความเร่งด่วน: ${cmdPriority}] หัวข้อ: ${cmdTitle}\n\nข้อความ: ${cmdDetails}`,
        location: 'ศูนย์สั่งการ บก.ทล.',
      };

      const res = await fetch('/api/reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'mission', data }),
      });
      const result = await res.json();
      if (res.ok && result.status === 'success') {
        Swal.fire({
          icon: 'success',
          title: 'ส่งข้อสั่งการสำเร็จ',
          text: 'ข้อสั่งการได้รับการบันทึกและส่งไปยังวิทยุสื่อสารประจำหน่วยเรียบร้อย',
          background: '#0a0b10',
          color: '#ffffff'
        });
        setCmdTitle('');
        setCmdDetails('');
      } else {
        Swal.fire({
          icon: 'error',
          title: 'เกิดข้อผิดพลาด',
          text: result.message || 'บันทึกข้อมูลล้มเหลว',
          background: '#0a0b10',
          color: '#ffffff'
        });
      }
    } catch (err) {
      Swal.fire({
        icon: 'error',
        title: 'เกิดข้อผิดพลาด',
        text: 'ไม่สามารถบันทึกข้อสั่งการได้',
        background: '#0a0b10',
        color: '#ffffff'
      });
    } finally {
      setFormLoading(false);
    }
  };

  const handleSendRadio = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!radioMessage) return;

    Swal.fire({
      title: 'กำลังส่งสัญญาณวิทยุ...',
      html: `ส่งข้อความไปยังช่อง <b>${radioChannel}</b>...`,
      allowOutsideClick: false,
      didOpen: () => {
        Swal.showLoading();
      }
    });

    setTimeout(() => {
      Swal.fire({
        icon: 'success',
        title: 'ส่งสัญญาณวิทยุเรียบร้อย',
        text: 'เสียงและข้อความวิทยุถูกถ่ายทอดผ่านศูนย์รับส่งสัญญาณดาวเทียมไปยังรถวิทยุตรวจการณ์ทั่วประเทศแล้ว',
        background: '#0a0b10',
        color: '#ffffff'
      });
      setRadioMessage('');
    }, 1500);
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginLoading(true);

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUser, password: loginPass }),
      });
      const result = await res.json();

      if (res.ok && result.status === 'success') {
        setUser(result.user);
        Swal.fire({
          icon: 'success',
          title: 'เข้าสู่ระบบสำเร็จ',
          text: `สิทธิ์การเข้าถึง: ${result.user.role}`,
          timer: 1500,
          showConfirmButton: false,
          background: '#0a0b10',
          color: '#ffffff'
        });
        routeUserDefault(result.user);
      } else {
        Swal.fire({
          icon: 'error',
          title: 'เข้าสู่ระบบไม่สำเร็จ',
          text: result.message || 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง',
          background: '#0a0b10',
          color: '#ffffff'
        });
      }
    } catch (err) {
      Swal.fire({
        icon: 'error',
        title: 'เกิดข้อผิดพลาด',
        text: 'เชื่อมต่อฐานข้อมูลล้มเหลว',
        background: '#0a0b10',
        color: '#ffffff'
      });
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
      setUser(null);
      setLoginUser('');
      setLoginPass('');
      setCurrentView('login');
      Swal.fire({
        icon: 'success',
        title: 'ออกจากระบบแล้ว',
        timer: 1000,
        showConfirmButton: false,
        background: '#0a0b10',
        color: '#ffffff'
      });
    } catch (err) {
      console.error(err);
    }
  };

  const setNow = (setter: React.Dispatch<React.SetStateAction<string>>) => {
    const tzoffset = (new Date()).getTimezoneOffset() * 60000;
    const localISOTime = (new Date(Date.now() - tzoffset)).toISOString().slice(0, 16);
    setter(localISOTime);
  };

  const submitReport = async (type: string, data: any) => {
    setFormLoading(true);
    try {
      const res = await fetch('/api/reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, data }),
      });
      const result = await res.json();
      if (res.ok && result.status === 'success') {
        Swal.fire({
          icon: 'success',
          title: 'บันทึกสำเร็จ',
          text: `เลขที่ใบงาน: ${result.data.recordId}`,
          background: '#0a0b10',
          color: '#ffffff'
        });
        routeUserDefault(user!);
      } else {
        Swal.fire({
          icon: 'error',
          title: 'ล้มเหลว',
          text: result.message || 'บันทึกข้อมูลล้มเหลว',
          background: '#0a0b10',
          color: '#ffffff'
        });
      }
    } catch (err) {
      Swal.fire({
        icon: 'error',
        title: 'เกิดข้อผิดพลาด',
        text: 'ไม่สามารถเขียนฐานข้อมูลได้',
        background: '#0a0b10',
        color: '#ffffff'
      });
    } finally {
      setFormLoading(false);
    }
  };

  const fetchPendingQueue = async () => {
    setPendingLoading(true);
    try {
      const res = await fetch('/api/admin/pending?type=general');
      const result = await res.json();
      if (res.ok && result.status === 'success') {
        setPendingItems(result.data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setPendingLoading(false);
    }
  };

  const fetchMyHistory = async () => {
    setHistoryLoading(true);
    try {
      // Re-use pending queue for demo, but filter by logged-in user in real app
      const res = await fetch('/api/admin/pending?type=general');
      const result = await res.json();
      if (res.ok && result.status === 'success') {
        const filtered = (result.data as PendingItem[]).filter(item => item.actionBy === user?.fullName || item.actionBy === user?.username);
        setHistoryItems(filtered);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleCancelMyItem = async (recordId: string, sheetName: string) => {
    Swal.fire({
      title: 'ต้องการยกเลิกรายงานนี้?',
      text: 'คุณสามารถยกเลิกรายงานก่อนที่แอดมินหรือสิบเวรจะทำการอนุมัติเพื่อนำไปกรอกข้อมูลใหม่ได้',
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: 'ยกเลิกรายการนี้',
      cancelButtonText: 'ย้อนกลับ',
      background: '#0a0b10',
      color: '#ffffff'
    }).then(async (result) => {
      if (result.isConfirmed) {
        try {
          const res = await fetch('/api/reports/cancel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ recordId, sheetName }),
          });
          const apiResult = await res.json();
          if (res.ok && apiResult.status === 'success') {
            Swal.fire({
              icon: 'success',
              title: 'ยกเลิกสำเร็จ',
              text: apiResult.message,
              background: '#0a0b10',
              color: '#ffffff'
            });
            fetchMyHistory();
          } else {
            Swal.fire({
              icon: 'error',
              title: 'ล้มเหลว',
              text: apiResult.message || 'ไม่พบรายการค้างส่งหรือได้รับการอนุมัติไปแล้ว',
              background: '#0a0b10',
              color: '#ffffff'
            });
          }
        } catch (err) {
          Swal.fire({
            icon: 'error',
            title: 'ผิดพลาด',
            text: 'ยกเลิกไม่สำเร็จ',
            background: '#0a0b10',
            color: '#ffffff'
          });
        }
      }
    });
  };

  const fetchMissions = async () => {
    try {
      const res = await fetch(`/api/reports?type=mission`);
      const result = await res.json();
      if (res.ok && result.status === 'success') {
        const filtered = (result.data as any[]).filter(m => {
          let matchesUnit = true;
          if (view_unitName) {
            matchesUnit = m.targetUnits.includes(view_unitName);
          }
          let matchesDate = true;
          if (view_startDate) {
            matchesDate = m.actualDate >= view_startDate;
          }
          if (view_endDate) {
            matchesDate = matchesDate && m.actualDate <= view_endDate;
          }
          return matchesUnit && matchesDate;
        });
        setMissionsList(filtered);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleAutoArrest = (e: React.FormEvent) => {
    e.preventDefault();
    Swal.fire({
      title: 'กำลังออกเอกสารอัตโนมัติ...',
      html: 'กรุณารอสักครู่ ระบบกำลังจัดหน้ากระดาษและกรอกฟอร์มตำรวจ...',
      timer: 2000,
      timerProgressBar: true,
      background: '#0a0b10',
      color: '#ffffff',
      didOpen: () => {
        Swal.showLoading();
      }
    }).then(() => {
      Swal.fire({
        icon: 'success',
        title: 'ออกเอกสารจับกุมเรียบร้อย!',
        text: `สร้างไฟล์พิมพ์เขียวสำเร็จสำหรับผู้ต้องหา ${aa_suspectName}`,
        background: '#0a0b10',
        color: '#ffffff'
      });
      setAaSuspectName('');
      setAaLocation('');
      setAaOffense('');
      setAaCircumstances('');
      setToolSubView('dashboard');
    });
  };

  const fetchHqDashboard = async (div?: string) => {
    setHqLoading(true);
    try {
      const url = div ? `/api/dashboards/hq?division=${div}` : '/api/dashboards/hq';
      const res = await fetch(url);
      const result = await res.json();
      if (res.ok && result.status === 'success') {
        setHqData(result.data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setHqLoading(false);
    }
  };

  const handleAdminAction = async (recordId: string, sheetName: string, action: 'approve' | 'void') => {
    Swal.fire({
      title: 'ยืนยันรายการอนุมัติ?',
      text: `คุณต้องการที่จะ ${action === 'approve' ? 'อนุมัติ' : 'ยกเลิก'} รายการคิวนี้ใช่หรือไม่?`,
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: 'ยืนยัน',
      cancelButtonText: 'ยกเลิก',
      background: '#0a0b10',
      color: '#ffffff'
    }).then(async (result) => {
      if (result.isConfirmed) {
        try {
          const res = await fetch('/api/admin/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ recordId, sheetName, action }),
          });
          const apiResult = await res.json();
          if (res.ok && apiResult.status === 'success') {
            Swal.fire({
              icon: 'success',
              title: 'ดำเนินการสำเร็จ',
              text: apiResult.message,
              background: '#0a0b10',
              color: '#ffffff'
            });
            fetchPendingQueue();
            fetchHqDashboard();
          } else {
            Swal.fire({
              icon: 'error',
              title: 'ทำรายการล้มเหลว',
              text: apiResult.message || 'เกิดข้อผิดพลาดในการตรวจสอบข้อมูล',
              background: '#0a0b10',
              color: '#ffffff'
            });
          }
        } catch (err) {
          Swal.fire({
            icon: 'error',
            title: 'ผิดพลาด',
            text: 'ไม่สามารถบันทึกข้อมูลลง SQL Database',
            background: '#0a0b10',
            color: '#ffffff'
          });
        }
      }
    });
  };

  const handleUnitCheckboxChange = (unit: string, checked: boolean) => {
    if (checked) {
      setMisUnits([...mis_units, unit]);
    } else {
      setMisUnits(mis_units.filter(u => u !== unit));
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-955 text-slate-100">
        <div className="text-center">
          <div className="spinner-border text-info mb-3"></div>
          <p className="text-info font-medium">กำลังเตรียมหน้าจอและตรวจสิทธิ์ผู้ใช้...</p>
        </div>
      </div>
    );
  }

  return (
    <main className="container-fluid min-h-screen py-4 flex items-center justify-center">

      {/* 1. Login View */}
      {currentView === 'login' && (
        <div className="glass-card" style={{ maxWidth: '400px' }}>
          <div className="title-area">
            <h2>HWPD NEXT GEN</h2>
            <p className="text-info small font-semibold">ระบบปฏิบัติการ กองบังคับการตำรวจทางหลวง</p>
          </div>
          <form onSubmit={handleLogin}>
            <div className="mb-3">
              <input
                type="text"
                required
                value={loginUser}
                onChange={(e) => setLoginUser(e.target.value)}
                className="form-control"
                placeholder="Username"
              />
            </div>
            <div className="mb-3">
              <input
                type="password"
                required
                value={loginPass}
                onChange={(e) => setLoginPass(e.target.value)}
                className="form-control"
                placeholder="Password"
              />
            </div>
            <button type="submit" disabled={loginLoading} className="btn-primary-custom">
              {loginLoading ? 'กำลังตรวจสอบ...' : 'เข้าสู่ระบบ'}
            </button>
          </form>
          <div className="text-center mt-3 text-xs text-white-50">
            ตัวอย่างสิทธิ์: staff51 (สายตรวจ), station51 (สิบเวร/สารวัตร), admin5 (ฝอ.กก.5)
          </div>
        </div>
      )}

      {/* 2. Unit Staff Main Menu */}
      {currentView === 'staff-menu' && user && (
        <div className="glass-card" style={{ maxWidth: '800px' }}>
          <div className="profile-section">
            <div className="profile-info">
              <h5>{user.fullName}</h5>
              <p><i className="fa-solid fa-location-dot me-1"></i>สถานี {user.station} ({user.unit})</p>
            </div>
            <div className="d-flex gap-2">
              {(user.role === 'Super_Commander' || user.role === 'HQ_Admin') && (
                <a
                  href="https://hwpd-invest-dashboard.vercel.app/?tab=result"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-outline-warning btn-sm d-inline-flex align-items-center"
                >
                  <i className="fa-solid fa-chart-pie me-1"></i> แผงควบคุม (ภายนอก)
                </a>
              )}
              {user.role === 'Division_Commander' && (
                <button
                  onClick={() => setCurrentView('commander-dashboard')}
                  className="btn btn-outline-warning btn-sm d-inline-flex align-items-center"
                >
                  <i className="fa-solid fa-chart-pie me-1"></i> แผงควบคุม
                </button>
              )}
              {(user.role === 'Station_Admin' || user.role === 'Division_Admin') && (
                <button
                  onClick={() => {
                    if (user.role === 'Station_Admin') {
                      setCurrentView('admin-dashboard');
                      fetchPendingQueue();
                    } else if (user.role === 'Division_Admin') {
                      setCurrentView('hq-dashboard');
                      setHqTab('pending');
                      fetchPendingQueue();
                    }
                  }}
                  className="btn btn-outline-info btn-sm d-inline-flex align-items-center"
                >
                  <i className="fa-solid fa-list-check me-1"></i> อนุมัติรายงาน
                </button>
              )}
              <button onClick={handleLogout} className="btn btn-outline-danger btn-sm" title="ออกจากระบบ">
                <i className="fa-solid fa-power-off"></i>
              </button>
            </div>
          </div>

          <h6 className="mb-3 text-white-50"><i className="fa-solid fa-bars me-1"></i> เมนูการปฏิบัติงาน</h6>
          
          <div className="menu-grid">
            <div className="menu-btn" onClick={() => { setCurrentView('formDaily'); setDailySubTab('tab1'); }}>
              <i className="fa-solid fa-clipboard-list"></i>
              <div className="mt-1 text-sm font-semibold">รายงานประจำวัน</div>
            </div>
            <div className="menu-btn" onClick={() => setCurrentView('formCheckpoint')}>
              <i className="fa-solid fa-road-barrier"></i>
              <div className="mt-1 text-sm font-semibold">รายงานตั้งด่าน</div>
            </div>
            <div className="menu-btn" onClick={() => setCurrentView('formArrest')}>
              <i className="fa-solid fa-handcuffs"></i>
              <div className="mt-1 text-sm font-semibold">รายงานจับกุม</div>
            </div>
            <div className="menu-btn" onClick={() => setCurrentView('formAccident')}>
              <i className="fa-solid fa-car-burst"></i>
              <div className="mt-1 text-sm font-semibold">รายงานอุบัติเหตุ</div>
            </div>
            <div className="menu-btn" onClick={() => setCurrentView('formMission')}>
              <i className="fa-solid fa-bullseye"></i>
              <div className="mt-1 text-sm font-semibold">แจ้งภารกิจ</div>
            </div>
            <div className="menu-btn" onClick={() => { setCurrentView('formMissionView'); fetchMissions(); }}>
              <i className="fa-solid fa-list-check"></i>
              <div className="mt-1 text-sm font-semibold">เรียกดูภารกิจ</div>
            </div>
            <div className="menu-btn" onClick={() => setCurrentView('formInventory')}>
              <i className="fa-solid fa-boxes-stacked"></i>
              <div className="mt-1 text-sm font-semibold">พัสดุ / แจ้งซ่อม</div>
            </div>
            <div className="menu-btn" onClick={() => setCurrentView('formDocument')}>
              <i className="fa-solid fa-file-signature"></i>
              <div className="mt-1 text-sm font-semibold">บันทึกข้อความ</div>
            </div>
            <div className="menu-btn" onClick={() => setCurrentView('formRoyalGuard')}>
              <i className="fa-solid fa-shield-halved"></i>
              <div className="mt-1 text-sm font-semibold">รายงานรับเสด็จ</div>
            </div>
            <div className="menu-btn" onClick={() => { setCurrentView('formFuel'); setFuelSubTab('refuel'); }}>
              <i className="fa-solid fa-gas-pump"></i>
              <div className="mt-1 text-sm font-semibold">น้ำมัน/น้ำมันเครื่อง</div>
            </div>
            <div className="menu-btn" onClick={() => { setCurrentView('formMyHistory'); fetchMyHistory(); }}>
              <i className="fa-solid fa-clock-rotate-left"></i>
              <div className="mt-1 text-sm font-semibold">ประวัติของฉัน</div>
            </div>
            <div className="menu-btn" onClick={() => { setCurrentView('formTools'); setToolSubView('dashboard'); }}>
              <i className="fa-solid fa-toolbox"></i>
              <div className="mt-1 text-sm font-semibold">เครื่องมือการทำงาน</div>
            </div>
          </div>
        </div>
      )}

      {/* 3. Daily Report Form */}
      {currentView === 'formDaily' && user && (
        <div className="glass-card" style={{ maxWidth: '900px' }}>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <button className="btn btn-sm btn-outline-info" onClick={() => setCurrentView('staff-menu')}>
              <i className="fa-solid fa-arrow-left me-1"></i> กลับเมนูหลัก
            </button>
            <h4 className="text-info m-0 font-bold">หมวดรายงานประจำวัน HWPD</h4>
            <div></div>
          </div>

          <ul className="nav nav-pills mb-4 justify-content-center">
            <li className="nav-item">
              <button className={`nav-link ${dailySubTab === 'tab1' ? 'active' : ''}`} onClick={() => setDailySubTab('tab1')}>
                เวรผลัด
              </button>
            </li>
            <li className="nav-item">
              <button className={`nav-link ${dailySubTab === 'tab2' ? 'active' : ''}`} onClick={() => setDailySubTab('tab2')}>
                ผลปฏิบัติ
              </button>
            </li>
          </ul>

          {dailySubTab === 'tab1' && (
            <form onSubmit={(e) => { e.preventDefault(); submitReport('daily-duty', { dr_reportDateTime, dr_unitId, dr_dutyOfficer, dr_dutyPhone, dr_carNumber }); }} className="row g-3">
              <div className="col-md-6">
                <label className="form-label small text-white-50">วันที่เวลาที่รายงาน</label>
                <div className="d-flex gap-2">
                  <input type="datetime-local" required value={dr_reportDateTime} onChange={(e) => setDrReportDateTime(e.target.value)} className="form-control" />
                  <button type="button" className="btn btn-outline-info flex-shrink-0" onClick={() => setNow(setDrReportDateTime)}>เวลาปัจจุบัน</button>
                </div>
              </div>
              <div className="col-md-6">
                <label className="form-label small text-white-50">หน่วยบริการ</label>
                <select required value={dr_unitId} onChange={(e) => setDrUnitId(e.target.value)} className="form-select">
                  <option value="">-- เลือกหน่วยบริการ --</option>
                  {unitsInStation.map(unit => (
                    <option key={unit} value={unit}>{unit}</option>
                  ))}
                </select>
              </div>
              <div className="col-md-8">
                <label className="form-label small text-white-50">ผู้ปฏิบัติหน้าที่ประจำหน่วย</label>
                <input type="text" required value={dr_dutyOfficer} onChange={(e) => setDrDutyOfficer(e.target.value)} placeholder="ยศ ชื่อ สกุล" className="form-control" />
              </div>
              <div className="col-md-4">
                <label className="form-label small text-white-50">เบอร์โทรศัพท์</label>
                <input type="tel" value={dr_dutyPhone} onChange={(e) => setDrDutyPhone(e.target.value)} className="form-control" placeholder="08x-xxxxxxx" />
              </div>
              <div className="col-12">
                <button type="submit" disabled={formLoading} className="btn-primary-custom">บันทึกรายงานเวรผลัด</button>
              </div>
            </form>
          )}

          {dailySubTab === 'tab2' && (
            <form onSubmit={(e) => { e.preventDefault(); submitReport('daily', { v43: res_v43, service: res_service, v42: res_v42, v20: res_v20, chargesText: res_chargesText, notes: res_notes }); }} className="row g-3">
              <div className="col-md-3 col-6">
                <label className="form-label small text-white-50">ว.43 (ครั้ง)</label>
                <input type="number" value={res_v43} onChange={(e) => setResV43(e.target.value)} className="form-control text-center" />
              </div>
              <div className="col-md-3 col-6">
                <label className="form-label small text-white-50">บริการ (ครั้ง)</label>
                <input type="number" value={res_service} onChange={(e) => setResVService(e.target.value)} className="form-control text-center" />
              </div>
              <div className="col-md-3 col-6">
                <label className="form-label small text-white-50">ว.42 (ครั้ง)</label>
                <input type="number" value={res_v42} onChange={(e) => setResV42(e.target.value)} className="form-control text-center" />
              </div>
              <div className="col-md-3 col-6">
                <label className="form-label small text-warning font-bold">ว.20 (ครั้ง)</label>
                <input type="number" value={res_v20} onChange={(e) => setResV20(e.target.value)} className="form-control text-center border-warning text-warning" />
              </div>
              <div className="col-12">
                <label className="form-label small text-white-50">รายละเอียดข้อหา/การดำเนินคดี</label>
                <textarea rows={3} value={res_chargesText} onChange={(e) => setResChargesText(e.target.value)} className="form-control" />
              </div>
              <div className="col-12">
                <button type="submit" disabled={formLoading} className="btn-primary-custom">บันทึกผลปฏิบัติงาน</button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* 4. Checkpoint Form */}
      {currentView === 'formCheckpoint' && user && (
        <div className="glass-card" style={{ maxWidth: '800px' }}>
          <div className="d-flex justify-content-between align-items-center mb-4">
            <button className="btn btn-sm btn-outline-info" onClick={() => setCurrentView('staff-menu')}>
              <i className="fa-solid fa-arrow-left me-1"></i> กลับ
            </button>
            <h4 className="text-info m-0 font-bold">รายงานด่าน จุดตรวจ จุดสกัด</h4>
            <div></div>
          </div>

          <form onSubmit={(e) => { e.preventDefault(); submitReport('checkpoint', { reportDateTime: chk_reportDateTime, unitId: chk_unitId, dutyOfficer: chk_dutyOfficer, totalPersonnel: chk_totalPersonnel, carNumber: chk_carNumber, location: chk_location === 'อื่นๆ' ? chk_locationOther : chk_location }); }} className="row g-3">
            <div className="col-md-6">
              <label className="form-label small text-white-50">วันที่เวลาที่รายงาน</label>
              <div className="d-flex gap-2">
                <input type="datetime-local" required value={chk_reportDateTime} onChange={(e) => setChkReportDateTime(e.target.value)} className="form-control" />
                <button type="button" className="btn btn-outline-info flex-shrink-0" onClick={() => setNow(setChkReportDateTime)}>เวลาปัจจุบัน</button>
              </div>
            </div>
            <div className="col-md-6">
              <label className="form-label small text-white-50">หน่วยบริการ</label>
              <select required value={chk_unitId} onChange={(e) => setChkUnitId(e.target.value)} className="form-select">
                <option value="">-- เลือกหน่วยบริการ --</option>
                {unitsInStation.map(unit => (
                  <option key={unit} value={unit}>{unit}</option>
                ))}
              </select>
            </div>
            <div className="col-md-8">
              <label className="form-label small text-white-50">ผู้ปฏิบัติหน้าที่ประจำหน่วย</label>
              <input type="text" required value={chk_dutyOfficer} onChange={(e) => setChkDutyOfficer(e.target.value)} placeholder="ยศ ชื่อ สกุล" className="form-control" />
            </div>
            <div className="col-md-4">
              <label className="form-label small text-white-50">จำนวนผู้ปฏิบัติรวม (นาย)</label>
              <input type="number" required value={chk_totalPersonnel} onChange={(e) => setChkTotalPersonnel(e.target.value)} className="form-control text-center" />
            </div>
            <div className="col-md-12">
              <label className="form-label small text-white-50">รถวิทยุตรวจเขต</label>
              <input type="text" required value={chk_carNumber} onChange={(e) => setChkCarNumber(e.target.value)} className="form-control" />
            </div>
            <div className="col-md-12">
              <label className="form-label small text-white-50">สถานที่ตั้งด่าน</label>
              <select required value={chk_location} onChange={(e) => setChkLocation(e.target.value)} className="form-select">
                <option value="">-- เลือกสถานที่ --</option>
                <option value="หน้าหน่วยบริการสามเงา ทล.1 กม 571-572 ต.วังจันทร์ อ.สามเงา จ.ตาก">หน้าหน่วยสามเงา ทล.1 กม 571-572</option>
                <option value="หน้าหน่วยฯ คลองขลุง ทล.1 กม. 414-415 ต.คลองขลุง อ.คลองขลุง จ.กำแพงเพชร">หน้าหน่วยฯ คลองขลุง ทล.1 กม. 414-415</option>
                <option value="อื่นๆ">อื่นๆ (ระบุเอง)</option>
              </select>
            </div>
            {chk_location === 'อื่นๆ' && (
              <div className="col-md-12">
                <label className="form-label small text-white-50">ระบุสถานที่อื่นๆ</label>
                <input type="text" required value={chk_locationOther} onChange={(e) => setChkLocationOther(e.target.value)} className="form-control border-info" placeholder="กรอกสถานที่" />
              </div>
            )}
            <div className="col-12 mt-4">
              <button type="submit" disabled={formLoading} className="btn-primary-custom">ส่งรายงานการตั้งด่าน</button>
            </div>
          </form>
        </div>
      )}

      {/* 5. Arrest Form */}
      {currentView === 'formArrest' && user && (
        <div className="glass-card" style={{ maxWidth: '800px' }}>
          <div className="d-flex justify-content-between align-items-center mb-4">
            <button className="btn btn-sm btn-outline-info" onClick={() => setCurrentView('staff-menu')}>
              <i className="fa-solid fa-arrow-left me-1"></i> กลับ
            </button>
            <h4 className="text-info m-0 font-bold">รายงานบันทึกการจับกุมผู้ต้องหา</h4>
            <div></div>
          </div>

          <form onSubmit={(e) => { e.preventDefault(); submitReport('arrest', { reportDateTime: arr_reportDateTime, unitId: arr_unitId, suspectCount: arr_suspectCount, suspectsText: arr_suspectsText, offense: arr_offense, circumstances: arr_circumstances }); }} className="row g-3">
            <div className="col-md-6">
              <label className="form-label small text-white-50">วันที่เวลาที่จับกุม</label>
              <div className="d-flex gap-2">
                <input type="datetime-local" required value={arr_reportDateTime} onChange={(e) => setArrReportDateTime(e.target.value)} className="form-control" />
                <button type="button" className="btn btn-outline-info flex-shrink-0" onClick={() => setNow(setArrReportDateTime)}>เวลาปัจจุบัน</button>
              </div>
            </div>
            <div className="col-md-6">
              <label className="form-label small text-white-50">หน่วยบริการที่รายงาน</label>
              <select required value={arr_unitId} onChange={(e) => setArrUnitId(e.target.value)} className="form-select">
                <option value="">-- เลือกหน่วยบริการ --</option>
                {unitsInStation.map(unit => (
                  <option key={unit} value={unit}>{unit}</option>
                ))}
              </select>
            </div>
            <div className="col-md-3">
              <label className="form-label small text-white-50">จำนวนผู้ต้องหา (คน)</label>
              <input type="number" required min="1" value={arr_suspectCount} onChange={(e) => setArrSuspectCount(e.target.value)} className="form-control text-center" />
            </div>
            <div className="col-md-9">
              <label className="form-label small text-white-50">ชื่อผู้ต้องหา (คั่นด้วยคอมมา `,` )</label>
              <input type="text" required value={arr_suspectsText} onChange={(e) => setArrSuspectsText(e.target.value)} placeholder="เช่น นายแดง มารวย" className="form-control" />
            </div>
            <div className="col-12">
              <label className="form-label small text-white-50">ข้อกล่าวหา</label>
              <input type="text" required value={arr_offense} onChange={(e) => setArrOffense(e.target.value)} placeholder="เช่น ขับรถโดยประมาท" className="form-control" />
            </div>
            <div className="col-12">
              <label className="form-label small text-white-50">พฤติการณ์จับกุม</label>
              <textarea rows={3} required value={arr_circumstances} onChange={(e) => setArrCircumstances(e.target.value)} className="form-control" />
            </div>
            <div className="col-12">
              <button type="submit" disabled={formLoading} className="btn-primary-custom">ส่งรายงานการจับกุม</button>
            </div>
          </form>
        </div>
      )}

      {/* 6. Accident Form */}
      {currentView === 'formAccident' && user && (
        <div className="glass-card" style={{ maxWidth: '850px' }}>
          <div className="d-flex justify-content-between align-items-center mb-4">
            <button className="btn btn-sm btn-outline-info" onClick={() => setCurrentView('staff-menu')}>
              <i className="fa-solid fa-arrow-left me-1"></i> กลับ
            </button>
            <h4 className="text-info m-0 font-bold">รายงานบันทึกการเกิดอุบัติเหตุทางถนน</h4>
            <div></div>
          </div>

          <form onSubmit={(e) => { e.preventDefault(); submitReport('accident', { reportDateTime: acc_reportDateTime, unitId: acc_unitId, route: acc_route, km: acc_km, direction: acc_direction, locDetails: acc_locDetails, deadCount: acc_deadCount, injuredCount: acc_injuredCount, hospital: acc_hospital, mainVehicle: acc_mainVehicle, oppVehicle: acc_oppVehicle }); }} className="row g-3">
            <div className="col-md-6">
              <label className="form-label small text-white-50">วันเวลาเกิดเหตุ</label>
              <div className="d-flex gap-2">
                <input type="datetime-local" required value={acc_reportDateTime} onChange={(e) => setAccReportDateTime(e.target.value)} className="form-control" />
                <button type="button" className="btn btn-outline-info flex-shrink-0" onClick={() => setNow(setAccReportDateTime)}>เวลาปัจจุบัน</button>
              </div>
            </div>
            <div className="col-md-6">
              <label className="form-label small text-white-50">หน่วยบริการ</label>
              <select required value={acc_unitId} onChange={(e) => setAccUnitId(e.target.value)} className="form-select">
                <option value="">-- เลือกหน่วยบริการ --</option>
                {unitsInStation.map(unit => (
                  <option key={unit} value={unit}>{unit}</option>
                ))}
              </select>
            </div>
            <div className="col-md-4">
              <label className="form-label small text-white-50">เส้นทางหลวง (เช่น ทล.1)</label>
              <input type="text" required value={acc_route} onChange={(e) => setAccRoute(e.target.value)} className="form-control text-center" />
            </div>
            <div className="col-md-4">
              <label className="form-label small text-white-50">กิโลเมตร (กม.)</label>
              <input type="text" required value={acc_km} onChange={(e) => setAccKm(e.target.value)} className="form-control text-center" />
            </div>
            <div className="col-md-4">
              <label className="form-label small text-white-50">ทิศทางจราจร</label>
              <input type="text" required value={acc_direction} onChange={(e) => setAccDirection(e.target.value)} placeholder="เช่น ขาเข้ากรุงเทพ" className="form-control text-center" />
            </div>
            <div className="col-md-6 col-6">
              <label className="form-label small text-white-50">จำนวนผู้เสียชีวิต (คน)</label>
              <input type="number" value={acc_deadCount} onChange={(e) => setAccDeadCount(e.target.value)} className="form-control text-center border-danger text-danger font-bold" />
            </div>
            <div className="col-md-6 col-6">
              <label className="form-label small text-white-50">จำนวนผู้บาดเจ็บ (คน)</label>
              <input type="number" value={acc_injuredCount} onChange={(e) => setAccInjuredCount(e.target.value)} className="form-control text-center border-warning text-warning font-bold" />
            </div>
            <div className="col-md-6">
              <label className="form-label small text-white-50">คู่กรณีที่ 1</label>
              <input type="text" required value={acc_mainVehicle} onChange={(e) => setAccMainVehicle(e.target.value)} className="form-control" />
            </div>
            <div className="col-md-6">
              <label className="form-label small text-white-50">คู่กรณีที่ 2</label>
              <input type="text" required value={acc_oppVehicle} onChange={(e) => setAccOppVehicle(e.target.value)} className="form-control" />
            </div>
            <div className="col-12">
              <label className="form-label small text-white-50">พฤติการณ์อุบัติเหตุเบื้องต้น</label>
              <textarea rows={3} required value={acc_locDetails} onChange={(e) => setAccLocDetails(e.target.value)} className="form-control" />
            </div>
            <div className="col-12">
              <button type="submit" disabled={formLoading} className="btn-primary-custom">ส่งรายงานอุบัติเหตุ</button>
            </div>
          </form>
        </div>
      )}

      {/* 7. Fuel Form */}
      {currentView === 'formFuel' && user && (
        <div className="glass-card" style={{ maxWidth: '800px' }}>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <button className="btn btn-sm btn-outline-warning" onClick={() => setCurrentView('staff-menu')}>
              <i className="fa-solid fa-arrow-left me-1"></i> กลับเมนูหลัก
            </button>
            <h4 className="text-white m-0 font-bold"><i className="fa-solid fa-gas-pump text-warning me-1"></i> น้ำมัน/น้ำมันเครื่อง</h4>
            <div></div>
          </div>

          <ul className="nav nav-pills mb-4 justify-content-center">
            <li className="nav-item">
              <button className={`nav-link ${fuelSubTab === 'refuel' ? 'active' : ''}`} onClick={() => setFuelSubTab('refuel')}>
                1. เติมน้ำมัน
              </button>
            </li>
            <li className="nav-item">
              <button className={`nav-link ${fuelSubTab === 'oil' ? 'active' : ''}`} onClick={() => setFuelSubTab('oil')}>
                2. เปลี่ยนน้ำมันเครื่อง
              </button>
            </li>
          </ul>

          <form onSubmit={(e) => { e.preventDefault(); submitReport('fuel', { recordType: fuelSubTab === 'refuel' ? 'เติมน้ำมัน' : 'เปลี่ยนน้ำมันเครื่อง', actionDateTime: fuel_actionDateTime, actionPerson: fuel_actionPerson, plateNumber: fuel_plateNumber, currentMileage: fuel_currentMileage, fuelType: fuel_type, liters: fuel_liters, price: fuel_price, receiptNumber: fuel_receiptNumber }); }} className="row g-3">
            <div className="col-md-6">
              <label className="form-label small text-white-50">วันเวลาที่ดำเนินงาน</label>
              <div className="d-flex gap-2">
                <input type="datetime-local" required value={fuel_actionDateTime} onChange={(e) => setFuelActionDateTime(e.target.value)} className="form-control" />
                <button type="button" className="btn btn-outline-warning flex-shrink-0" onClick={() => setNow(setFuelActionDateTime)}>เวลาปัจจุบัน</button>
              </div>
            </div>
            <div className="col-md-6">
              <label className="form-label small text-white-50">ผู้เติม/เปลี่ยนน้ำมันเครื่อง</label>
              <input type="text" required value={fuel_actionPerson} onChange={(e) => setFuelActionPerson(e.target.value)} className="form-control border-warning" />
            </div>
            <div className="col-md-6">
              <label className="form-label small text-white-50">ทะเบียนรถ</label>
              <input type="text" required value={fuel_plateNumber} onChange={(e) => setFuelPlateNumber(e.target.value)} className="form-control" placeholder="เช่น กท 1234" />
            </div>
            <div className="col-md-6">
              <label className="form-label small text-white-50">เลขไมล์</label>
              <input type="number" required value={fuel_currentMileage} onChange={(e) => setFuelCurrentMileage(e.target.value)} className="form-control" />
            </div>
            {fuelSubTab === 'refuel' && (
              <>
                <div className="col-md-4">
                  <label className="form-label small text-white-50">ประเภทน้ำมัน</label>
                  <select required value={fuel_type} onChange={(e) => setFuelType(e.target.value)} className="form-select">
                    <option value="">-- เลือกประเภท --</option>
                    <option value="ดีเซล">ดีเซล</option>
                    <option value="แก๊สโซฮอล์ 91">แก๊สโซฮอล์ 91</option>
                    <option value="แก๊สโซฮอล์ 95">แก๊สโซฮอล์ 95</option>
                  </select>
                </div>
                <div className="col-md-4 col-6">
                  <label className="form-label small text-white-50">จำนวน (ลิตร)</label>
                  <input type="number" step="0.001" required value={fuel_liters} onChange={(e) => setFuelLiters(e.target.value)} className="form-control text-center" />
                </div>
                <div className="col-md-4 col-6">
                  <label className="form-label small text-white-50">ราคา (บาท)</label>
                  <input type="number" step="0.1" required value={fuel_price} onChange={(e) => setFuelPrice(e.target.value)} className="form-control text-center border-success" />
                </div>
                <div className="col-12">
                  <label className="form-label small text-white-50">เลขที่ใบเสร็จ</label>
                  <input type="text" required value={fuel_receiptNumber} onChange={(e) => setFuelReceiptNumber(e.target.value)} className="form-control" />
                </div>
              </>
            )}
            <div className="col-12 mt-4">
              <button type="submit" disabled={formLoading} className="btn btn-warning w-100 py-3 font-bold text-dark rounded-xl">
                บันทึกรายงานน้ำมัน
              </button>
            </div>
          </form>
        </div>
      )}

      {/* 5. Set Mission Form */}
      {currentView === 'formMission' && user && (
        <div className="glass-card" style={{ maxWidth: '800px' }}>
          <div className="d-flex justify-content-between align-items-center mb-4">
            <button className="btn btn-sm btn-outline-info" onClick={() => setCurrentView('staff-menu')}>
              <i className="fa-solid fa-arrow-left me-1"></i> กลับเมนูหลัก
            </button>
            <h4 className="text-success m-0 font-bold"><i className="fa-solid fa-bullseye me-1"></i> แจ้งภารกิจ</h4>
            <div></div>
          </div>

          <form onSubmit={(e) => { e.preventDefault(); submitReport('mission', { reportDateTime: mis_reportDateTime, startTime: mis_startTime, endTime: mis_endTime, targetUnits: mis_units.join(', '), missionDetails: mis_details, location: mis_location }); }} className="row g-3">
            <div className="col-md-12">
              <label className="form-label small text-white-50">วันที่เวลาที่บันทึก</label>
              <div className="d-flex gap-2">
                <input type="datetime-local" required value={mis_reportDateTime} onChange={(e) => setMisReportDateTime(e.target.value)} className="form-control" />
                <button type="button" className="btn btn-outline-success flex-shrink-0" onClick={() => setNow(setMisReportDateTime)}>เวลาปัจจุบัน</button>
              </div>
            </div>
            <div className="col-md-6">
              <label className="form-label small text-white-50">เวลาเริ่มภารกิจ</label>
              <input type="datetime-local" required value={mis_startTime} onChange={(e) => setMisStartTime(e.target.value)} className="form-control border-success" />
            </div>
            <div className="col-md-6">
              <label className="form-label small text-white-50">เวลาสิ้นสุดภารกิจ</label>
              <input type="datetime-local" required value={mis_endTime} onChange={(e) => setMisEndTime(e.target.value)} className="form-control border-success" />
            </div>
            <div className="col-md-12">
              <label className="form-label small text-success font-bold mb-2">หน่วยบริการที่เกี่ยวข้อง (เลือกได้หลายหน่วย)</label>
              <div className="p-3 rounded border border-success/30 bg-success/5">
                <div className="row">
                  {unitsInStation.map(unit => (
                    <div key={unit} className="col-6 col-md-4">
                      <div className="form-check">
                        <input
                          type="checkbox"
                          className="form-check-input"
                          id={`unit-${unit}`}
                          onChange={(e) => handleUnitCheckboxChange(unit, e.target.checked)}
                        />
                        <label className="form-check-label text-slate-300 text-sm cursor-pointer" htmlFor={`unit-${unit}`}>{unit}</label>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="col-12">
              <label className="form-label small text-white-50">รายละเอียดภารกิจ</label>
              <textarea rows={3} required value={mis_details} onChange={(e) => setMisDetails(e.target.value)} className="form-control" placeholder="ระบุคำสั่งปฏิบัติงาน..." />
            </div>
            <div className="col-12">
              <label className="form-label small text-white-50">สถานที่ปฏิบัติงาน</label>
              <input type="text" required value={mis_location} onChange={(e) => setMisLocation(e.target.value)} className="form-control" placeholder="ระบุชื่อพิกัด/สถานที่" />
            </div>
            <div className="col-12 mt-4">
              <button type="submit" disabled={formLoading} className="btn btn-success w-100 py-3 font-bold">ยืนยันแจ้งภารกิจ</button>
            </div>
          </form>
        </div>
      )}

      {/* 6. Mission View Form */}
      {currentView === 'formMissionView' && user && (
        <div className="glass-card" style={{ maxWidth: '800px' }}>
          <div className="d-flex justify-content-between align-items-center mb-4">
            <button className="btn btn-sm btn-outline-info" onClick={() => setCurrentView('staff-menu')}>
              <i className="fa-solid fa-arrow-left me-1"></i> กลับหน้าหลัก
            </button>
            <h4 className="text-info m-0 font-bold"><i className="fa-solid fa-list-check me-1"></i> เรียกดูภารกิจหน่วย</h4>
            <div></div>
          </div>

          <div className="row g-3 mb-4">
            <div className="col-md-4">
              <label className="form-label small text-white-50">หน่วยบริการ</label>
              <select value={view_unitName} onChange={(e) => setViewUnitName(e.target.value)} className="form-select">
                <option value="">-- ทุกหน่วย --</option>
                {unitsInStation.map(unit => (
                  <option key={unit} value={unit}>{unit}</option>
                ))}
              </select>
            </div>
            <div className="col-md-4">
              <label className="form-label small text-white-50">ตั้งแต่</label>
              <input type="date" value={view_startDate} onChange={(e) => setViewStartDate(e.target.value)} className="form-control" />
            </div>
            <div className="col-md-4">
              <label className="form-label small text-white-50">ถึงวันที่</label>
              <input type="date" value={view_endDate} onChange={(e) => setViewEndDate(e.target.value)} className="form-control" />
            </div>
            <div className="col-12 mt-4">
              <button onClick={fetchMissions} className="btn btn-info w-100 font-bold text-dark py-2.5">
                <i className="fa-solid fa-magnifying-glass me-1"></i> ค้นหาภารกิจในระบบ
              </button>
            </div>
          </div>

          {/* Search Result */}
          <div className="p-3 rounded border border-info/30 bg-info/5">
            <h6 className="text-info mb-3"><i className="fa-solid fa-calendar-check me-1"></i> รายการภารกิจที่พบ</h6>
            {missionsList.length === 0 ? (
              <div className="text-center py-4 text-white-50">ไม่พบข้อมูลภารกิจตามตัวเลือก</div>
            ) : (
              <div className="d-flex flex-col gap-3">
                {missionsList.map(m => (
                  <div key={m.recordId} className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg">
                    <div className="d-flex justify-content-between align-items-center">
                      <span className="font-bold text-info text-sm">{m.location}</span>
                      <span className="font-mono text-[10px] text-amber-500">{m.recordId}</span>
                    </div>
                    <p className="text-xs text-slate-300 mt-2 mb-1">{m.missionDetails}</p>
                    <small className="text-[10px] text-white-50">
                      หน่วยที่ปฏิบัติ: {m.targetUnits} • เริ่มต้น: {m.startTime} ถึง {m.endTime}
                    </small>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 7. Inventory & Repair Form */}
      {currentView === 'formInventory' && user && (
        <div className="glass-card" style={{ maxWidth: '850px' }}>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <button className="btn btn-sm btn-outline-info" onClick={() => setCurrentView('staff-menu')}>
              <i className="fa-solid fa-arrow-left me-1"></i> กลับเมนูหลัก
            </button>
            <h4 className="text-white m-0 font-bold"><i className="fa-solid fa-boxes-stacked text-warning me-1"></i> ทรัพย์สิน / แจ้งซ่อม</h4>
            <div></div>
          </div>

          <ul className="nav nav-pills mb-4 justify-content-center">
            <li className="nav-item">
              <button className={`nav-link ${invSubTab === 'my-assets' ? 'active' : ''}`} onClick={() => setInvSubTab('my-assets')}>
                1. สินทรัพย์ในครอบครอง
              </button>
            </li>
            <li className="nav-item">
              <button className={`nav-link ${invSubTab === 'repair' ? 'active' : ''}`} onClick={() => setInvSubTab('repair')}>
                2. แจ้งซ่อมบำรุง
              </button>
            </li>
          </ul>

          {invSubTab === 'my-assets' && (
            <div className="text-center py-4 bg-slate-900/40 rounded-xl border border-slate-800">
              <i className="fa-solid fa-box-open text-info text-4xl mb-3 block"></i>
              <span className="badge bg-info text-dark px-3 py-1.5 font-bold mb-3">ผู้ลงทะเบียน: {user.fullName}</span>
              <p className="text-slate-400 text-sm">ยังไม่มีรายการทรัพย์สินลงทะเบียนครอบครองในสิทธิ์ SQLite เครื่องของคุณ</p>
            </div>
          )}

          {invSubTab === 'repair' && (
            <form onSubmit={(e) => { e.preventDefault(); submitReport('repair', { reportDateTime: rep_reportDateTime, brokenItem: rep_brokenItem, reporterName: rep_reporterName, issueDetail: rep_issueDetail }); }} className="row g-3">
              <div className="col-md-12">
                <label className="form-label small text-white-50">วันเวลาที่แจ้งซ่อม</label>
                <div className="d-flex gap-2">
                  <input type="datetime-local" required value={rep_reportDateTime} onChange={(e) => setRepReportDateTime(e.target.value)} className="form-control" />
                  <button type="button" className="btn btn-outline-warning flex-shrink-0" onClick={() => setNow(setRepReportDateTime)}>เวลาปัจจุบัน</button>
                </div>
              </div>
              <div className="col-md-6">
                <label className="form-label small text-white-50">สินทรัพย์/พัสดุ ที่ชำรุด</label>
                <input type="text" required value={rep_brokenItem} onChange={(e) => setRepBrokenItem(e.target.value)} placeholder="ระบุชื่อหรือรหัสครุภัณฑ์" className="form-control border-warning" />
              </div>
              <div className="col-md-6">
                <label className="form-label small text-white-50">ผู้แจ้ง</label>
                <input type="text" required value={rep_reporterName} onChange={(e) => setRepReporterName(e.target.value)} className="form-control" />
              </div>
              <div className="col-md-12">
                <label className="form-label small text-white-50">อาการเสีย/อาการชำรุดเบื้องต้น</label>
                <textarea rows={3} required value={rep_issueDetail} onChange={(e) => setRepIssueDetail(e.target.value)} placeholder="เช่น แอร์เปิดไม่ติด น้ำยารั่ว..." className="form-control" />
              </div>
              <div className="col-12 mt-4">
                <button type="submit" disabled={formLoading} className="btn btn-warning text-dark w-100 py-2.5 font-bold rounded-xl">แจ้งซ่อมบำรุง</button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* 8. Online Document Form */}
      {currentView === 'formDocument' && user && (
        <div className="glass-card" style={{ maxWidth: '600px' }}>
          <div className="d-flex justify-content-between align-items-center mb-4">
            <button className="btn btn-sm btn-outline-info" onClick={() => setCurrentView('staff-menu')}>
              <i className="fa-solid fa-arrow-left me-1"></i> กลับ
            </button>
            <h4 className="text-info m-0 font-bold"><i className="fa-solid fa-file-signature me-1"></i> เซ็นเอกสารออนไลน์</h4>
            <div></div>
          </div>

          <form onSubmit={(e) => { e.preventDefault(); submitReport('document', { reportDateTime: doc_reportDateTime, subject: doc_subject, docType: doc_type, senderName: doc_senderName }); }} className="row g-3">
            <div className="col-md-12">
              <label className="form-label small text-white-50">วันเวลาส่งหนังสือ</label>
              <div className="d-flex gap-2">
                <input type="datetime-local" required value={doc_reportDateTime} onChange={(e) => setDocReportDateTime(e.target.value)} className="form-control" />
                <button type="button" className="btn btn-outline-info flex-shrink-0" onClick={() => setNow(setDocReportDateTime)}>เวลาปัจจุบัน</button>
              </div>
            </div>
            <div className="col-md-12">
              <label className="form-label small text-white-50">เรื่อง/หัวข้อหนังสือ</label>
              <input type="text" required value={doc_subject} onChange={(e) => setDocSubject(e.target.value)} className="form-control border-info" placeholder="เช่น ขออนุมัติเบิกพัสดุประจำเดือน" />
            </div>
            <div className="col-md-12">
              <label className="form-label small text-white-50">ประเภทหนังสือ</label>
              <select value={doc_type} onChange={(e) => setDocType(e.target.value)} className="form-select">
                <option value="บันทึกข้อความ">บันทึกข้อความ</option>
                <option value="หนังสือราชการส่งภายนอก">หนังสือราชการส่งภายนอก</option>
                <option value="แบบขออนุมัติ">แบบขออนุมัติ</option>
              </select>
            </div>
            <div className="col-md-12">
              <label className="form-label small text-white-50">ผู้ส่งเอกสาร</label>
              <input type="text" required value={doc_senderName} onChange={(e) => setDocSenderName(e.target.value)} className="form-control" />
            </div>
            <div className="col-12 mt-4">
              <button type="submit" disabled={formLoading} className="btn-primary-custom">นำเข้าหนังสือระบบออนไลน์</button>
            </div>
          </form>
        </div>
      )}

      {/* 9. Royal Guard Form */}
      {currentView === 'formRoyalGuard' && user && (
        <div className="glass-card" style={{ maxWidth: '700px' }}>
          <div className="d-flex justify-content-between align-items-center mb-4 border-bottom border-info pb-2">
            <button className="btn btn-sm btn-outline-info" onClick={() => setCurrentView('staff-menu')}>
              <i className="fa-solid fa-arrow-left me-1"></i> กลับเมนูหลัก
            </button>
            <h4 className="text-info m-0 font-bold"><i className="fa-solid fa-shield-halved me-1"></i> หมวดรายงานรับเสด็จ</h4>
            <div></div>
          </div>

          <div className="btn-group w-100 mb-4">
            <button className={`btn ${rg_type === 'prep' ? 'btn-warning' : 'btn-outline-warning'}`} onClick={() => setRgType('prep')}>
              1. ปล่อยแถวรับเสด็จ
            </button>
            <button className={`btn ${rg_type === 'complete' ? 'btn-success' : 'btn-outline-success'}`} onClick={() => setRgType('complete')}>
              2. เสร็จสิ้นภารกิจ
            </button>
          </div>

          <form onSubmit={(e) => { e.preventDefault(); submitReport('royal-guard', { reportType: rg_type, reportDateTime: rg_dateTime, missionName: rg_missionName, commanders: rg_commanders, carNumbers: rg_carNumbers, targetCount: rg_targetCount, details: rg_details }); }} className="row g-3">
            <div className="col-md-6">
              <label className="form-label small text-warning">วันที่และเวลา</label>
              <div className="d-flex gap-2">
                <input type="datetime-local" required value={rg_dateTime} onChange={(e) => setRgDateTime(e.target.value)} className="form-control" />
                <button type="button" className="btn btn-outline-warning flex-shrink-0" onClick={() => setNow(setRgDateTime)}>เวลาปัจจุบัน</button>
              </div>
            </div>
            <div className="col-md-6">
              <label className="form-label small text-warning">ชื่อภารกิจถวายความปลอดภัย</label>
              <input type="text" required value={rg_missionName} onChange={(e) => setRgMissionName(e.target.value)} className="form-control" placeholder="เช่น เดโชชัย 5..." />
            </div>
            <div className="col-md-12">
              <label className="form-label small text-info">รายชื่อผู้บังคับบัญชาคุมจุดตรวจ</label>
              <input type="text" required value={rg_commanders} onChange={(e) => setRgCommanders(e.target.value)} className="form-control" placeholder="ยศ ชื่อ สกุล" />
            </div>
            {rg_type === 'complete' && (
              <>
                <div className="col-md-6">
                  <label className="form-label small text-warning">รถวิทยุที่เกี่ยวข้อง</label>
                  <input type="text" value={rg_carNumbers} onChange={(e) => setRgCarNumbers(e.target.value)} className="form-control" placeholder="เช่น 5101, 5102" />
                </div>
                <div className="col-md-6">
                  <label className="form-label small text-warning">จำนวนที่หมายในพื้นที่ตนเอง (แห่ง)</label>
                  <input type="number" value={rg_targetCount} onChange={(e) => setRgTargetCount(e.target.value)} className="form-control text-center" />
                </div>
              </>
            )}
            <div className="col-md-12">
              <label className="form-label small text-warning">ภารกิจของพระองค์</label>
              <textarea rows={3} required value={rg_details} onChange={(e) => setRgDetails(e.target.value)} placeholder="ระบุพฤติการณ์ภารกิจการเสด็จ..." className="form-control" />
            </div>
            <div className="col-12 mt-4">
              <button type="submit" disabled={formLoading} className="btn btn-info text-dark w-100 py-3 font-bold">
                ส่งรายงานถวายความปลอดภัย
              </button>
            </div>
          </form>
        </div>
      )}

      {/* 11. My History View */}
      {currentView === 'formMyHistory' && user && (
        <div className="glass-card" style={{ maxWidth: '900px' }}>
          <div className="d-flex justify-content-between align-items-center mb-4">
            <button className="btn btn-sm btn-outline-info" onClick={() => setCurrentView('staff-menu')}>
              <i className="fa-solid fa-arrow-left me-1"></i> กลับเมนูหลัก
            </button>
            <h4 className="text-white m-0 font-bold"><i className="fa-solid fa-clock-rotate-left text-info me-1"></i> ประวัติการส่งของฉัน</h4>
            <div></div>
          </div>

          <div className="p-3 bg-slate-900/40 rounded-xl border border-slate-800">
            <div className="d-flex justify-content-between align-items-center mb-3">
              <h5 className="text-info m-0 font-semibold">รายการรอตรวจสอบอนุมัติ (Pending)</h5>
              <button className="btn btn-sm btn-outline-info" onClick={fetchMyHistory}><i className="fa-solid fa-rotate me-1"></i> รีเฟรช</button>
            </div>

            <div className="alert bg-cyan-900/10 border border-cyan-500/30 text-cyan-200 text-xs mb-4">
              <i className="fa-solid fa-circle-info me-1"></i> รายงานที่ค้างอนุมัติ หากกรอกข้อมูลผิดพลาด คุณสามารถกดยกเลิกรายการเองได้เพื่อกรอกข้อมูลใหม่
            </div>

            {historyLoading ? (
              <div className="text-center py-4"><span className="spinner-border spinner-border-sm text-info me-2"></span> กำลังดึงข้อมูล...</div>
            ) : historyItems.length === 0 ? (
              <div className="text-center py-5 text-white-50">ไม่มีประวัติงานค้างอนุมัติในบัญชีนี้</div>
            ) : (
              <div className="table-responsive">
                <table className="table table-dark table-striped table-bordered border-slate-800 text-center m-0">
                  <thead>
                    <tr className="border-info">
                      <th>วันที่ส่งรายงาน</th>
                      <th>หมวดหมู่รายงาน</th>
                      <th>เลขที่เอกสาร</th>
                      <th>จัดการ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historyItems.map(item => (
                      <tr key={item.recordId}>
                        <td>{new Date(item.timestamp).toLocaleString('th-TH')}</td>
                        <td><span className="badge bg-info text-dark font-bold">{item.formType}</span></td>
                        <td className="font-mono text-xs text-amber-400">{item.recordId}</td>
                        <td>
                          <button onClick={() => handleCancelMyItem(item.recordId, item.sheetName)} className="btn btn-xs btn-outline-danger">
                            <i className="fa-solid fa-trash-can me-1"></i> ยกเลิก
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 12. Working Tools View */}
      {currentView === 'formTools' && user && (
        <div className="glass-card" style={{ maxWidth: '900px' }}>
          {toolSubView === 'dashboard' && (
            <div>
              <div className="d-flex justify-content-between align-items-center border-bottom border-info pb-3 mb-4">
                <h4 className="mb-0 text-info font-bold"><i className="fa-solid fa-toolbox me-1"></i> เครื่องมือการทำงาน</h4>
                <button type="button" className="btn btn-outline-light btn-sm" onClick={() => setCurrentView('staff-menu')}>
                  <i className="fa-solid fa-arrow-left me-1"></i> กลับเมนูหลัก
                </button>
              </div>

              <div className="row g-3 mb-4">
                <div className="col-md-4">
                  <button className="btn-primary-custom py-4 w-100" onClick={() => setToolSubView('auto-arrest')}>
                    <i className="fa-solid fa-file-invoice text-warning fa-2x mb-2"></i><br />ออกเอกสารจับกุมอัตโนมัติ
                  </button>
                </div>
                <div className="col-md-4">
                  <a href="https://sites.google.com/view/case-study-hwpd/Home" target="_blank" rel="noreferrer" className="btn btn-outline-info w-100 py-4 d-flex flex-column align-items-center justify-content-center" style={{ borderRadius: '15px', height: '100%' }}>
                    <i className="fa-solid fa-book fa-2x mb-2 text-info"></i><span>คู่มือการทำงาน</span>
                  </a>
                </div>
                <div className="col-md-4">
                  <a href="https://secretive-sundae-24e.notion.site/5-2ddd6231c7bb80afb1f0eb3a129f3bc3?source=copy_link" target="_blank" rel="noreferrer" className="btn btn-outline-success w-100 py-4 d-flex flex-column align-items-center justify-content-center" style={{ borderRadius: '15px', height: '100%' }}>
                    <i className="fa-brands fa-google-drive fa-2x mb-2 text-emerald-400"></i><span>คลังฟอร์มเอกสาร</span>
                  </a>
                </div>
              </div>

              <h5 className="text-warning border-bottom border-secondary pb-2 mt-5">
                <i className="fa-solid fa-bullhorn me-1"></i> ประกาศข่าวสารจากผู้บังคับบัญชา
              </h5>
              <div className="mt-3 p-3 bg-slate-900/50 rounded-xl border border-slate-800">
                <div className="alert text-light border border-info mb-0" style={{ background: 'rgba(0, 242, 255, 0.05)' }}>
                  <small className="text-info"><i className="fa-regular fa-clock me-1"></i> ล่าสุดวันนี้</small><br />
                  <span className="badge bg-warning text-dark mb-1">ฝอ. บก.ทล.</span><br />
                  <strong>ระบบ HWPD Next Gen Standalone:</strong> ระบบได้รับการอัปเดตและปรับโครงสร้างการมองเห็นสิทธิ์ตามสถานีและประเภทกลุ่มผู้ใช้งานเสร็จสมบูรณ์เรียบร้อย ยินดีต้อนรับเข้าใช้งานครับ
                </div>
              </div>
            </div>
          )}

          {toolSubView === 'auto-arrest' && (
            <div>
              <div className="d-flex justify-content-between align-items-center border-bottom border-warning pb-3 mb-4">
                <h4 className="mb-0 text-warning font-bold"><i className="fa-solid fa-file-invoice me-1"></i> ออกเอกสารจับกุมอัตโนมัติ</h4>
                <button type="button" className="btn btn-outline-light btn-sm" onClick={() => setToolSubView('dashboard')}>
                  <i className="fa-solid fa-arrow-left me-1"></i> กลับ
                </button>
              </div>

              <form onSubmit={handleAutoArrest} className="row g-3">
                <div className="col-md-6">
                  <label className="form-label small text-white-50">วันเวลาที่ทำการจับกุม</label>
                  <input type="datetime-local" required value={aa_date} onChange={(e) => setAaDate(e.target.value)} className="form-control" />
                </div>
                <div className="col-md-6">
                  <label className="form-label small text-white-50">สถานที่จับกุม</label>
                  <input type="text" required value={aa_location} onChange={(e) => setAaLocation(e.target.value)} className="form-control" placeholder="เช่น ริมถนน ทล.1 กม. 351..." />
                </div>
                <div className="col-md-6">
                  <label className="form-label small text-white-50">ชื่อ-นามสกุล ผู้ต้องหา</label>
                  <input type="text" required value={aa_suspectName} onChange={(e) => setAaSuspectName(e.target.value)} className="form-control border-warning" placeholder="ระบุชื่อยศผู้ต้องหา..." />
                </div>
                <div className="col-md-6">
                  <label className="form-label small text-white-50">ข้อหาที่จับกุม</label>
                  <input type="text" required value={aa_offense} onChange={(e) => setAaOffense(e.target.value)} className="form-control" placeholder="เช่น มีเครื่องวิทยุคมนาคมโดยไม่ได้รับอนุญาต" />
                </div>
                <div className="col-md-12">
                  <label className="form-label small text-white-50">พฤติการณ์จับกุมโดยย่อ</label>
                  <textarea rows={3} required value={aa_circumstances} onChange={(e) => setAaCircumstances(e.target.value)} placeholder="ระบุพฤติการณ์การสังเกตการณ์ ค้นหา และการคุมตัวของสายตรวจ..." className="form-control" />
                </div>
                <div className="col-12 mt-4">
                  <button type="submit" className="btn btn-warning text-dark w-100 py-3 font-bold rounded-xl">
                    <i className="fa-solid fa-file-word me-1"></i> ประมวลผลและสร้างคำร้องใบจับกุมอัตโนมัติ (.docx)
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      )}

      {/* 13. Admin Dashboard View */}
      {currentView === 'admin-dashboard' && user && (
        <div className="glass-card" style={{ maxWidth: '850px', width: '100%' }}>
          <div className="profile-section">
            <div className="profile-info">
              <h5>{user.fullName}</h5>
              <p><i className="fa-solid fa-list-check me-1"></i>ระบบอนุมัติรายงานระดับสถานี {user.station}</p>
            </div>
            <div className="d-flex gap-2">
              <button onClick={() => setCurrentView('staff-menu')} className="btn btn-outline-info btn-sm">
                <i className="fa-solid fa-arrow-left me-1"></i> กลับเมนูหลัก
              </button>
              <button onClick={handleLogout} className="btn btn-outline-danger btn-sm">
                <i className="fa-solid fa-power-off"></i>
              </button>
            </div>
          </div>

          <div className="row g-4 mb-4">
            <div className="col-12">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <h5 className="text-info font-bold m-0"><i className="fa-solid fa-list-check me-2"></i>รายการค้างอนุมัติของ ส.ทล.{user.station}</h5>
                <button onClick={fetchPendingQueue} className="btn btn-sm btn-outline-info">
                  <i className="fa-solid fa-arrows-rotate me-1"></i> รีเฟรช
                </button>
              </div>
              
              {pendingLoading ? (
                <div className="text-center py-5">
                  <div className="spinner-border text-info"></div>
                </div>
              ) : pendingItems.length === 0 ? (
                <div className="py-5 text-center text-slate-500 bg-slate-900/40 rounded-xl border border-slate-800">
                  <i className="fa-regular fa-circle-check text-4xl mb-2 text-emerald-400 block"></i>
                  <span>ไม่มีข้อมูลรายงานค้างอนุมัติสำหรับสถานีนี้</span>
                </div>
              ) : (
                <div className="d-flex flex-column gap-3">
                  {pendingItems.map((item) => (
                    <div key={item.recordId} className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3">
                      <div>
                        <span className="badge bg-info text-dark font-bold me-2">{item.formType}</span>
                        <span className="font-mono text-xs text-amber-500 font-semibold">{item.recordId}</span>
                        <p className="text-xs text-slate-400 mt-2 m-0">ผู้ส่ง: {item.actionBy} • หน่วย: {item.unitId} • วันที่ส่ง: {new Date(item.timestamp).toLocaleString('th-TH')}</p>
                      </div>
                      <div className="d-flex gap-2">
                        <button onClick={() => handleAdminAction(item.recordId, item.sheetName, 'approve')} className="btn btn-sm btn-success px-3">อนุมัติ</button>
                        <button onClick={() => handleAdminAction(item.recordId, item.sheetName, 'void')} className="btn btn-sm btn-danger px-3">ลบ</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 14. HQ Dashboard View */}
      {currentView === 'hq-dashboard' && user && (
        <div className="glass-card" style={{ maxWidth: '900px', width: '100%' }}>
          <div className="profile-section">
            <div className="profile-info">
              <h5>{user.fullName}</h5>
              <p><i className="fa-solid fa-list-check me-1"></i>ระบบอนุมัติรายงานระดับกองกำกับการ {user.station[0]}</p>
            </div>
            <div className="d-flex gap-2">
              <button onClick={() => setCurrentView('staff-menu')} className="btn btn-outline-info btn-sm">
                <i className="fa-solid fa-arrow-left me-1"></i> กลับเมนูหลัก
              </button>
              <button onClick={handleLogout} className="btn btn-outline-danger btn-sm">
                <i className="fa-solid fa-power-off"></i>
              </button>
            </div>
          </div>

          <div className="p-2 mt-3">
            <h5 className="text-info font-bold mb-4"><i className="fa-solid fa-list-check me-2"></i>อนุมัติเอกสารค้างพิจารณา (ระดับกองกำกับการ)</h5>
            {pendingLoading ? (
              <div className="text-center py-5">
                <div className="spinner-border text-info"></div>
              </div>
            ) : pendingItems.length === 0 ? (
              <div className="py-5 text-center text-slate-500 bg-slate-900/40 rounded-xl border border-slate-800">
                <i className="fa-regular fa-circle-check text-4xl mb-2 text-emerald-400 block"></i>
                <span>ไม่มีข้อมูลรายงานค้างอนุมัติใน กองกำกับการ นี้</span>
              </div>
            ) : (
              <div className="d-flex flex-column gap-3">
                {pendingItems.map((item) => (
                  <div key={item.recordId} className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3">
                    <div>
                      <span className="badge bg-info text-dark font-bold me-2">{item.formType}</span>
                      <span className="font-mono text-xs text-amber-500 font-semibold">{item.recordId}</span>
                      <p className="text-xs text-slate-400 mt-2 m-0">ผู้ส่ง: {item.actionBy} • หน่วย: {item.unitId} • วันที่ส่ง: {new Date(item.timestamp).toLocaleString('th-TH')}</p>
                    </div>
                    <div className="d-flex gap-2">
                      <button onClick={() => handleAdminAction(item.recordId, item.sheetName, 'approve')} className="btn btn-sm btn-success px-3">อนุมัติ</button>
                      <button onClick={() => handleAdminAction(item.recordId, item.sheetName, 'void')} className="btn btn-sm btn-danger px-3">ลบ</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 15. Commander Dashboard View */}
      {currentView === 'commander-dashboard' && user && (
        <div className="glass-card" style={{ maxWidth: '900px', width: '100%' }}>
          <div className="profile-section">
            <div className="profile-info">
              <h5>{user.fullName}</h5>
              <p><i className="fa-solid fa-star me-1"></i>ผู้บังคับการ กองกำกับการ {user.station[0]} (สิทธิ์: {user.role})</p>
            </div>
            <div className="d-flex gap-2">
              <a href={getExternalDashboardUrl(user)} target="_blank" rel="noopener noreferrer" className="btn btn-warning btn-sm d-inline-flex align-items-center text-dark font-bold">
                <i className="fa-solid fa-chart-column me-1"></i> แดชบอร์ดงานสืบสวน
              </a>
              <button onClick={() => setCurrentView('staff-menu')} className="btn btn-outline-info btn-sm">
                <i className="fa-solid fa-pen-nib me-1"></i> ส่งรายงาน
              </button>
              <button onClick={handleLogout} className="btn btn-outline-danger btn-sm">
                <i className="fa-solid fa-power-off"></i>
              </button>
            </div>
          </div>

          <h5 className="text-info font-bold mb-4"><i className="fa-solid fa-chart-line me-2"></i>รายงานสรุปผลงานระดับผู้บังคับบัญชา (กก.{user.station[0]})</h5>

          {hqLoading ? (
            <div className="text-center py-5">
              <div className="spinner-border text-info"></div>
            </div>
          ) : hqData ? (
            <div>
              <div className="row g-4 mb-4">
                <div className="col-md-4 col-12">
                  <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-center">
                    <span className="text-white-50 text-xs block uppercase font-bold tracking-wider">คดีจับกุมสะสม</span>
                    <span className="text-4xl font-extrabold text-emerald-400 block mt-2">{hqData.totals.arrests}</span>
                  </div>
                </div>
                <div className="col-md-4 col-12">
                  <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-center">
                    <span className="text-white-50 text-xs block uppercase font-bold tracking-wider">อุบัติเหตุรวม</span>
                    <span className="text-4xl font-extrabold text-rose-500 block mt-2">{hqData.totals.accidents}</span>
                  </div>
                </div>
                <div className="col-md-4 col-12">
                  <div className="p-4 bg-info/10 border border-info/20 rounded-xl text-center">
                    <span className="text-white-50 text-xs block uppercase font-bold tracking-wider">ผลปฏิบัติงาน ว.20</span>
                    <span className="text-4xl font-extrabold text-info block mt-2">{hqData.totals.v20}</span>
                  </div>
                </div>
              </div>

              {/* Renders interactive ApexCharts! */}
              <div className="mt-4">
                <ExecutiveCharts stations={hqData.stations} />
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* 16. Super Commander Dashboard View */}
      {currentView === 'super-commander-dashboard' && user && (
        <div className="glass-card" style={{ maxWidth: '1350px', width: '100%' }}>
          <div className="profile-section">
            <div className="profile-info">
              <h5>{user.fullName}</h5>
              <p><i className="fa-solid fa-crown me-1"></i>ผู้บัญชาการตำรวจทางหลวง (สิทธิ์: {user.role})</p>
            </div>
            <div className="d-flex gap-2">
              <button onClick={() => setCurrentView('staff-menu')} className="btn btn-outline-info btn-sm">
                <i className="fa-solid fa-pen-nib me-1"></i> ส่งรายงาน
              </button>
              <button onClick={handleLogout} className="btn btn-outline-danger btn-sm">
                <i className="fa-solid fa-power-off"></i>
              </button>
            </div>
          </div>

          <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-3 gap-3 border-bottom border-slate-800 pb-3">
            <h5 className="text-info font-bold m-0"><i className="fa-solid fa-earth-asia me-2"></i>ระบบตรวจการแดชบอร์ดสืบสวนเชิงลึก บก.ทล.</h5>
            <span className="badge bg-warning text-dark font-bold text-xs"><i className="fa-solid fa-circle-nodes me-1"></i> LIVE DATABASE CONNECTION</span>
          </div>

          {/* Embedded Vercel Dashboard */}
          <div className="w-100 mb-4 rounded-xl overflow-hidden border border-slate-800 shadow-2xl position-relative d-flex flex-column align-items-center justify-content-center" style={{ height: '750px', backgroundColor: '#0f111a' }}>
            <div className="position-absolute top-3 end-3" style={{ zIndex: 10 }}>
              <a
                href="https://hwpd-invest-dashboard.vercel.app/?tab=result"
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-warning btn-sm text-dark font-bold px-3 py-2 shadow-lg"
              >
                <i className="fa-solid fa-up-right-from-square me-1"></i> เปิดในแท็บใหม่ (Open External)
              </a>
            </div>
            
            {/* Background Helper Text (Visible if Iframe is blocked/loading) */}
            <div className="text-center p-4 position-absolute text-slate-500" style={{ zIndex: 0 }}>
              <i className="fa-solid fa-shield-halved text-5xl mb-3 text-warning" style={{ opacity: 0.4 }}></i>
              <h6 className="text-slate-400 font-bold mb-2">ระบบกำลังดึงหน้าแดชบอร์ดจาก Server Vercel...</h6>
              <p className="text-xs max-w-md mx-auto leading-relaxed text-slate-500 m-0">
                หากหน้านี้แสดงเป็นช่องว่างเนื่องจากมาตรการความปลอดภัยของเบราว์เซอร์บล็อก iframe บน Localhost<br/>
                กรุณาคลิกปุ่ม <b>"เปิดในแท็บใหม่"</b> ที่มุมขวาบน เพื่อดูรายงานแยกหน้าจอต่างหากครับ
              </p>
            </div>

            <iframe
              src="https://hwpd-invest-dashboard.vercel.app/?tab=result"
              title="บก.ทล. แดชบอร์ดงานสืบสวน"
              className="position-relative w-100 h-100"
              style={{ border: 'none', background: 'transparent', zIndex: 1 }}
              allowFullScreen
            />
          </div>

          {/* บก.ทล. Command and Dispatch Center */}
          <div className="row g-4 mt-4 border-top border-slate-800 pt-4">
            {/* Left Column: Directives Form */}
            <div className="col-md-7 col-12">
              <div className="p-4 bg-slate-900/40 border border-slate-800 rounded-xl">
                <h5 className="text-warning font-bold mb-3 d-flex align-items-center">
                  <i className="fa-solid fa-bullhorn text-warning me-2 animate-bounce"></i>
                  <span>ศูนย์ข้อสั่งการ ผบก.ทล. (Commander Directive Center)</span>
                </h5>
                <p className="text-white-50 text-xs mb-4">
                  ส่งข้อสั่งการตรงไปยังหน่วยบริการทางหลวงทุกแห่งทั่วประเทศ ข้อความจะบันทึกลงในระบบการมอบหมายภารกิจโดยอัตโนมัติ
                </p>
                <form onSubmit={handleSendDirective} className="row g-3">
                  <div className="col-md-8">
                    <label className="form-label small text-white-50 font-bold mb-1">หัวข้อข้อสั่งการ</label>
                    <input
                      type="text"
                      required
                      value={cmdTitle}
                      onChange={(e) => setCmdTitle(e.target.value)}
                      placeholder="เช่น เพิ่มกำลังสายตรวจกวดขันวินัยจราจรช่วงสุดสัปดาห์"
                      className="form-control bg-slate-950 border-slate-700 text-white text-sm"
                    />
                  </div>
                  <div className="col-md-4">
                    <label className="form-label small text-white-50 font-bold mb-1">ระดับความเร่งด่วน</label>
                    <select
                      value={cmdPriority}
                      onChange={(e) => setCmdPriority(e.target.value)}
                      className="form-select bg-slate-950 border-slate-700 text-white text-sm"
                    >
                      <option value="ด่วนที่สุด">🚨 ด่วนที่สุด</option>
                      <option value="ด่วน">⚠️ ด่วน</option>
                      <option value="ปกติ">🟢 ปกติ</option>
                    </select>
                  </div>
                  <div className="col-md-12">
                    <label className="form-label small text-white-50 font-bold mb-1">เป้าหมายผู้รับปฏิบัติ</label>
                    <select
                      value={cmdTargetDiv}
                      onChange={(e) => setCmdTargetDiv(e.target.value)}
                      className="form-select bg-slate-950 border-slate-700 text-white text-sm"
                    >
                      <option value="all">ทุกกองกำกับการ (กก.1 - กก.8 ทั่วประเทศ)</option>
                      <option value="1">กองกำกับการ 1 (กก.1 บก.ทล.)</option>
                      <option value="2">กองกำกับการ 2 (กก.2 บก.ทล.)</option>
                      <option value="3">กองกำกับการ 3 (กก.3 บก.ทล.)</option>
                      <option value="4">กองกำกับการ 4 (กก.4 บก.ทล.)</option>
                      <option value="5">กองกำกับการ 5 (กก.5 บก.ทล.)</option>
                      <option value="6">กองกำกับการ 6 (กก.6 บก.ทล.)</option>
                      <option value="7">กองกำกับการ 7 (กก.7 บก.ทล.)</option>
                      <option value="8">กองกำกับการ 8 (กก.8 บก.ทล.)</option>
                    </select>
                  </div>
                  <div className="col-12">
                    <label className="form-label small text-white-50 font-bold mb-1">รายละเอียดข้อสั่งการและระเบียบปฏิบัติ</label>
                    <textarea
                      rows={4}
                      required
                      value={cmdDetails}
                      onChange={(e) => setCmdDetails(e.target.value)}
                      placeholder="ระบุแนวทางการปฏิบัติงาน กำลังพล วิธีปฏิบัติการ และรายงานสรุปผลงาน..."
                      className="form-control bg-slate-950 border-slate-700 text-white text-sm"
                    />
                  </div>
                  <div className="col-12 mt-3">
                    <button type="submit" disabled={formLoading} className="btn btn-warning text-dark w-100 font-bold py-2.5">
                      <i className="fa-solid fa-paper-plane me-1"></i> ประกาศสั่งการราชการไปยังทุกหน่วยงานย่อย
                    </button>
                  </div>
                </form>
              </div>
            </div>

            {/* Right Column: Radio Command & Satellite Dispatch */}
            <div className="col-md-5 col-12">
              <div className="p-4 bg-slate-900/40 border border-slate-800 rounded-xl d-flex flex-column h-100 justify-content-between">
                <div>
                  <h5 className="text-info font-bold mb-3 d-flex align-items-center">
                    <i className="fa-solid fa-tower-broadcast text-info me-2"></i>
                    <span>ส่งวิทยุสั่งการสายตรวจ (Radio Dispatcher)</span>
                  </h5>
                  <p className="text-white-50 text-xs mb-4">
                    พิมพ์สัญญาณ ว. ข้อความสั้นเพื่อประกาศถ่ายทอดไปยังรถสายตรวจทางหลวงขณะปฏิบัติหน้าที่
                  </p>
                  <form onSubmit={handleSendRadio} className="row g-3">
                    <div className="col-12">
                      <label className="form-label small text-white-50 font-bold mb-1">ช่องความถี่วิทยุ</label>
                      <select
                        value={radioChannel}
                        onChange={(e) => setRadioChannel(e.target.value)}
                        className="form-select bg-slate-950 border-slate-700 text-white text-sm"
                      >
                        <option value="ช่องวิทยุผ่านดาวเทียม (บก.ทล.)">📡 ช่องผ่านดาวเทียม บก.ทล. (ทั่วประเทศ)</option>
                        <option value="ช่องข่ายสื่อสาร กกก.1-4 (สายเหนือ-ตะวันออก)">📡 ข่ายเหนือ/ตะวันออก</option>
                        <option value="ช่องข่ายสื่อสาร กกก.5-8 (สายใต้-มอเตอร์เวย์)">📡 ข่ายใต้/มอเตอร์เวย์</option>
                      </select>
                    </div>
                    <div className="col-12">
                      <label className="form-label small text-white-50 font-bold mb-1">ข้อความสัญญาณวิทยุ (ว.10/ว.15)</label>
                      <textarea
                        rows={3}
                        required
                        value={radioMessage}
                        onChange={(e) => setRadioMessage(e.target.value)}
                        placeholder="ระบุข้อความแจ้งเตือนด่วน หรือคำสั่งแจ้ง ว.10 ประจำจุดตรวจ..."
                        className="form-control bg-slate-950 border-slate-700 text-white text-sm"
                      />
                    </div>
                    <div className="col-12 mt-3">
                      <button type="submit" className="btn btn-info text-dark w-100 font-bold py-2.5">
                        <i className="fa-solid fa-volume-high me-1"></i> ยิงสัญญาณเสียงวิทยุสื่อสารสะท้อนดาวเทียม
                      </button>
                    </div>
                  </form>
                </div>

                <div className="mt-4 p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-xs text-slate-400">
                  <div className="d-flex align-items-center mb-1 text-emerald-400 font-bold">
                    <span className="spinner-grow spinner-grow-sm me-2 text-emerald-400"></span>
                    <span>LINK STATUS: Connected to Satellites</span>
                  </div>
                  ระบบเชื่อมโยงข้อมูลตรงกับรถวิทยุสายตรวจ 43 สถานีทั่วประเทศในขณะนี้
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 17. HQ Admin Dashboard View */}
      {currentView === 'hq-admin-dashboard' && user && (
        <div className="glass-card text-center" style={{ maxWidth: '600px', width: '100%' }}>
          <div className="profile-section">
            <div className="profile-info">
              <h5>{user.fullName}</h5>
              <p><i className="fa-solid fa-users-gear me-1"></i>ระบบจัดการผู้ใช้ระดับประเทศ (สิทธิ์: {user.role})</p>
            </div>
            <div className="d-flex gap-2">
              <button onClick={() => setCurrentView('staff-menu')} className="btn btn-outline-info btn-sm">
                <i className="fa-solid fa-pen-nib me-1"></i> ส่งรายงาน
              </button>
              <button onClick={handleLogout} className="btn btn-outline-danger btn-sm">
                <i className="fa-solid fa-power-off"></i>
              </button>
            </div>
          </div>
          <i className="fa-solid fa-users-gear text-info text-5xl mb-4 mt-4"></i>
          <h3 className="text-xl font-bold">ระบบบริหารจัดการบัญชีตำรวจทางหลวง</h3>
          <p className="text-slate-400 mt-2 text-sm leading-relaxed">
            บัญชีรายชื่อของเจ้าหน้าที่ตำรวจทางหลวง กก.1 - กก.8 ทั้งหมดถูกบันทึกและควบคุมอย่างปลอดภัยผ่าน SQLite ฐานข้อมูลเดียว
          </p>
          <button className="btn btn-outline-info mt-4" onClick={() => Swal.fire({title:'แผงจัดการข้อมูลระบบเสร็จสมบูรณ์แล้ว', background:'#0a0b10', color:'#fff'})}>
            เรียกดูรายชื่อตำรวจทั้งหมด
          </button>
        </div>
      )}

    </main>
  );
}
