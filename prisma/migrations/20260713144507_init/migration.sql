-- CreateTable
CREATE TABLE "User" (
    "username" TEXT NOT NULL PRIMARY KEY,
    "password" TEXT NOT NULL,
    "fullName" TEXT NOT NULL,
    "station" TEXT NOT NULL,
    "unit" TEXT NOT NULL,
    "role" TEXT NOT NULL,
    "helpGoTo" TEXT,
    "helpFrom" TEXT,
    "note" TEXT,
    "phone" TEXT,
    "code" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "Charge" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "name" TEXT NOT NULL
);

-- CreateTable
CREATE TABLE "DailyResult" (
    "recordId" TEXT NOT NULL PRIMARY KEY,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "actionBy" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "actualDate" TEXT NOT NULL,
    "stationId" TEXT NOT NULL,
    "unitId" TEXT NOT NULL,
    "reportDateTime" TEXT NOT NULL,
    "v43" INTEGER NOT NULL,
    "service" INTEGER NOT NULL,
    "v42" INTEGER NOT NULL,
    "v20" INTEGER NOT NULL,
    "chargesText" TEXT NOT NULL,
    "mapLink" TEXT,
    "signatureUrl" TEXT,
    "notes" TEXT,
    "folderUrl" TEXT
);

-- CreateTable
CREATE TABLE "Arrest" (
    "recordId" TEXT NOT NULL PRIMARY KEY,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "actionBy" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "actualDate" TEXT NOT NULL,
    "stationId" TEXT NOT NULL,
    "unitId" TEXT NOT NULL,
    "reportDateTime" TEXT NOT NULL,
    "suspectCount" INTEGER NOT NULL,
    "suspectsText" TEXT NOT NULL,
    "offense" TEXT NOT NULL,
    "circumstances" TEXT NOT NULL,
    "mapLink" TEXT,
    "folderUrl" TEXT
);

-- CreateTable
CREATE TABLE "Accident" (
    "recordId" TEXT NOT NULL PRIMARY KEY,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "actionBy" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "actualDate" TEXT NOT NULL,
    "stationId" TEXT NOT NULL,
    "unitId" TEXT NOT NULL,
    "reportDateTime" TEXT NOT NULL,
    "route" TEXT NOT NULL,
    "km" TEXT NOT NULL,
    "direction" TEXT NOT NULL,
    "locDetails" TEXT NOT NULL,
    "deadCount" INTEGER NOT NULL,
    "injuredCount" INTEGER NOT NULL,
    "hospital" TEXT,
    "mainVehicle" TEXT NOT NULL,
    "oppVehicle" TEXT NOT NULL,
    "cHuman" REAL NOT NULL,
    "cVehicle" REAL NOT NULL,
    "cRoad" REAL NOT NULL,
    "cEnv" REAL NOT NULL,
    "solutions" TEXT,
    "govDamage" TEXT,
    "carNumber" TEXT,
    "jointUnits" TEXT,
    "description" TEXT,
    "lat" TEXT,
    "lng" TEXT,
    "folderUrl" TEXT
);

-- CreateTable
CREATE TABLE "OtherDuty" (
    "recordId" TEXT NOT NULL PRIMARY KEY,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "actionBy" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "actualDate" TEXT NOT NULL,
    "stationId" TEXT NOT NULL,
    "unitId" TEXT NOT NULL,
    "dutyType" TEXT NOT NULL,
    "details" TEXT NOT NULL,
    "location" TEXT NOT NULL,
    "folderUrl" TEXT
);

-- CreateTable
CREATE TABLE "RoyalGuard" (
    "recordId" TEXT NOT NULL PRIMARY KEY,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "actionBy" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "actualDate" TEXT NOT NULL,
    "stationId" TEXT NOT NULL,
    "unitId" TEXT NOT NULL,
    "reportType" TEXT NOT NULL,
    "reportDateTime" TEXT NOT NULL,
    "commanders" TEXT NOT NULL,
    "missionName" TEXT NOT NULL,
    "carNumbers" TEXT NOT NULL,
    "details" TEXT NOT NULL,
    "folderUrl" TEXT,
    "targetCount" INTEGER NOT NULL
);

-- CreateTable
CREATE TABLE "Mission" (
    "recordId" TEXT NOT NULL PRIMARY KEY,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "actionBy" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "actualDate" TEXT NOT NULL,
    "stationId" TEXT NOT NULL,
    "unitId" TEXT NOT NULL,
    "reportDateTime" TEXT NOT NULL,
    "startTime" TEXT NOT NULL,
    "endTime" TEXT NOT NULL,
    "targetUnits" TEXT NOT NULL,
    "missionDetails" TEXT NOT NULL,
    "location" TEXT NOT NULL,
    "folderUrl" TEXT
);

-- CreateTable
CREATE TABLE "Inventory" (
    "recordId" TEXT NOT NULL PRIMARY KEY,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "actionBy" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "actualDate" TEXT NOT NULL,
    "stationId" TEXT NOT NULL,
    "unitId" TEXT NOT NULL,
    "actionDateTime" TEXT NOT NULL,
    "transactionType" TEXT NOT NULL,
    "category" TEXT NOT NULL,
    "itemName" TEXT NOT NULL,
    "qty" REAL NOT NULL,
    "unitMeasure" TEXT NOT NULL,
    "receiverName" TEXT NOT NULL,
    "signatureUrl" TEXT,
    "notes" TEXT
);

-- CreateTable
CREATE TABLE "Repair" (
    "recordId" TEXT NOT NULL PRIMARY KEY,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "actionBy" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "actualDate" TEXT NOT NULL,
    "stationId" TEXT NOT NULL,
    "unitId" TEXT NOT NULL,
    "reportDateTime" TEXT NOT NULL,
    "brokenItem" TEXT NOT NULL,
    "issueDetail" TEXT NOT NULL,
    "reporterName" TEXT NOT NULL,
    "repairStatus" TEXT NOT NULL,
    "folderUrl" TEXT
);

-- CreateTable
CREATE TABLE "OnlineDocument" (
    "recordId" TEXT NOT NULL PRIMARY KEY,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "actionBy" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "actualDate" TEXT NOT NULL,
    "stationId" TEXT NOT NULL,
    "unitId" TEXT NOT NULL,
    "reportDateTime" TEXT NOT NULL,
    "subject" TEXT NOT NULL,
    "docType" TEXT NOT NULL,
    "senderName" TEXT NOT NULL,
    "docStatus" TEXT NOT NULL,
    "fileUrl" TEXT
);

-- CreateTable
CREATE TABLE "FuelOil" (
    "recordId" TEXT NOT NULL PRIMARY KEY,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "actionBy" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "actualDate" TEXT NOT NULL,
    "stationId" TEXT NOT NULL,
    "unitId" TEXT NOT NULL,
    "recordType" TEXT NOT NULL,
    "actionDateTime" TEXT NOT NULL,
    "actionPerson" TEXT NOT NULL,
    "plateNumber" TEXT NOT NULL,
    "currentMileage" REAL NOT NULL,
    "liters" REAL NOT NULL,
    "fuelType" TEXT,
    "price" REAL,
    "receiptNumber" TEXT,
    "prevMileage" REAL,
    "distanceUsed" REAL
);

-- CreateTable
CREATE TABLE "FuelQuota" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "monthYear" TEXT NOT NULL,
    "stationId" TEXT NOT NULL,
    "quotaLiters" REAL NOT NULL,
    "quotaBaht" REAL NOT NULL,
    "quotaOilLiters" REAL NOT NULL,
    "lastUpdate" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "actionBy" TEXT NOT NULL
);

-- CreateTable
CREATE TABLE "NationalSummary" (
    "recordId" TEXT NOT NULL PRIMARY KEY,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "actionBy" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "dateStr" TEXT NOT NULL,
    "div" TEXT NOT NULL,
    "divName" TEXT NOT NULL,
    "arrestsCount" INTEGER NOT NULL,
    "v20Count" INTEGER NOT NULL,
    "v43Count" INTEGER NOT NULL,
    "v42Count" INTEGER NOT NULL,
    "serviceCount" INTEGER NOT NULL,
    "accCount" INTEGER NOT NULL,
    "deadCount" INTEGER NOT NULL,
    "injuredCount" INTEGER NOT NULL,
    "volCount" INTEGER NOT NULL,
    "royalCount" INTEGER NOT NULL,
    "missionCount" INTEGER NOT NULL,
    "jsonArrest" TEXT NOT NULL,
    "jsonCharge" TEXT NOT NULL,
    "jsonAccCause" TEXT NOT NULL
);

-- CreateIndex
CREATE UNIQUE INDEX "Charge_name_key" ON "Charge"("name");
