#import <CoreBluetooth/CoreBluetooth.h>
#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#import <fcntl.h>
#import <signal.h>
#import <sys/file.h>
#import <unistd.h>

static NSData *effectPayloadFromJson(NSString *json);

@interface Logger : NSObject
@property(nonatomic, strong) NSString *path;
- (void)write:(NSString *)line;
@end

@implementation Logger
- (instancetype)init {
    self = [super init];
    if (!self) { return nil; }
    NSString *dir = [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Logs/TenonCodexLight"];
    [[NSFileManager defaultManager] createDirectoryAtPath:dir withIntermediateDirectories:YES attributes:nil error:nil];
    self.path = [dir stringByAppendingPathComponent:@"scan.log"];
    [@"" writeToFile:self.path atomically:YES encoding:NSUTF8StringEncoding error:nil];
    return self;
}

- (void)write:(NSString *)line {
    printf("%s\n", [line UTF8String]);
    NSString *entry = [line stringByAppendingString:@"\n"];
    NSFileHandle *handle = [NSFileHandle fileHandleForWritingAtPath:self.path];
    if (handle) {
        [handle seekToEndOfFile];
        [handle writeData:[entry dataUsingEncoding:NSUTF8StringEncoding]];
        [handle closeFile];
    } else {
        [entry writeToFile:self.path atomically:YES encoding:NSUTF8StringEncoding error:nil];
    }
}
@end

@interface PeripheralRecord : NSObject
@property(nonatomic, strong) CBPeripheral *peripheral;
@property(nonatomic, copy) NSString *name;
@property(nonatomic) NSInteger rssi;
@property(nonatomic, strong) NSArray<CBUUID *> *advertisedServices;
@property(nonatomic) BOOL manufacturerDataPresent;
@property(nonatomic, strong) NSArray<CBUUID *> *serviceDataUUIDs;
@property(nonatomic, strong) NSArray<CBService *> *discoveredServices;
@property(nonatomic, strong) NSMutableDictionary<NSString *, NSArray<CBCharacteristic *> *> *discoveredCharacteristics;
@property(nonatomic, copy) NSString *serviceDiscoveryError;
@end

@implementation PeripheralRecord
@end

@interface ScanDelegate : NSObject <CBCentralManagerDelegate, CBPeripheralDelegate>
@property(nonatomic, strong) CBCentralManager *central;
@property(nonatomic, strong) Logger *logger;
@property(nonatomic) NSTimeInterval duration;
@property(nonatomic) BOOL includeServices;
@property(nonatomic) BOOL verbose;
@property(nonatomic) BOOL didScheduleFinish;
@property(nonatomic, strong) NSMutableDictionary<NSUUID *, PeripheralRecord *> *records;
@property(nonatomic, strong) NSMutableSet<NSUUID *> *pendingServiceDiscovery;
@property(nonatomic, strong) NSMutableSet<NSString *> *pendingCharacteristicDiscovery;
@property(nonatomic) BOOL writeColor;
@property(nonatomic, strong) NSUUID *targetIdentifier;
@property(nonatomic, strong) CBUUID *targetServiceUUID;
@property(nonatomic, strong) CBUUID *targetCharacteristicUUID;
@property(nonatomic, strong) NSData *writePayload;
@property(nonatomic) CBCharacteristicWriteType writeType;
@property(nonatomic, strong) CBPeripheral *writePeripheral;
@property(nonatomic) BOOL writeEffect;
@property(nonatomic, copy) NSString *effectName;
@property(nonatomic) NSInteger effectActionType;
@property(nonatomic, copy) NSString *effectJson;
@property(nonatomic) BOOL daemonMode;
@property(nonatomic) BOOL daemonOnce;
@property(nonatomic, copy) NSString *stateFilePath;
@property(nonatomic, copy) NSString *lockFilePath;
@property(nonatomic) int lockFileDescriptor;
@property(nonatomic, copy) NSString *lastState;
@property(nonatomic, copy) NSString *pendingState;
@property(nonatomic) NSTimeInterval pollInterval;
@property(nonatomic) BOOL verboseIdentifiers;
@property(nonatomic) BOOL cleanupInProgress;
@property(nonatomic) int pendingExitCode;
@property(nonatomic) BOOL effectsDisabled;
@property(nonatomic) BOOL pendingEffectWrite;
@property(nonatomic, strong) NSData *pendingFallbackPayload;
@property(nonatomic, copy) NSString *pendingMode;
@property(nonatomic, copy) NSString *pendingPresetName;
@end

@implementation ScanDelegate
- (instancetype)initWithDuration:(NSTimeInterval)duration includeServices:(BOOL)includeServices verbose:(BOOL)verbose logger:(Logger *)logger {
    self = [super init];
    if (!self) { return nil; }
    self.duration = duration;
    self.includeServices = includeServices;
    self.verbose = verbose;
    self.logger = logger;
    self.records = [NSMutableDictionary dictionary];
    self.pendingServiceDiscovery = [NSMutableSet set];
    self.pendingCharacteristicDiscovery = [NSMutableSet set];
    self.lockFileDescriptor = -1;
    return self;
}

- (void)start {
    self.central = [[CBCentralManager alloc] initWithDelegate:self queue:dispatch_get_main_queue()];
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(8 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
        if (self.central.state == CBManagerStateUnknown) {
            [self.logger write:@"bluetooth_state: unknown_timeout"];
            [self finish:2];
        }
    });
}

- (void)centralManagerDidUpdateState:(CBCentralManager *)central {
    switch (central.state) {
        case CBManagerStatePoweredOn:
            [self.logger write:@"bluetooth_state: poweredOn"];
            if (self.writeColor) {
                [self startWriteProbe];
            } else if (self.daemonMode) {
                [self startDaemon];
            } else {
                [self startScan];
            }
            break;
        case CBManagerStatePoweredOff:
            [self.logger write:@"bluetooth_state: poweredOff"];
            [self finish:2];
            break;
        case CBManagerStateUnauthorized:
            [self.logger write:@"bluetooth_state: unauthorized"];
            [self.logger write:@"Open System Settings -> Privacy & Security -> Bluetooth and allow Tenon Codex Light Scan."];
            [self finish:2];
            break;
        case CBManagerStateUnsupported:
            [self.logger write:@"bluetooth_state: unsupported"];
            [self finish:2];
            break;
        case CBManagerStateResetting:
            [self.logger write:@"bluetooth_state: resetting"];
            break;
        case CBManagerStateUnknown:
        default:
            [self.logger write:@"bluetooth_state: unknown"];
            break;
    }
}

- (void)startDaemon {
    if (![self acquireDaemonLock]) {
        [self.logger write:@"daemon_error: another daemon is already running for this state file and device"];
        [self finishWithoutCleanup:1];
        return;
    }
    [self.logger write:@"daemon: started"];
    [self.logger write:[NSString stringWithFormat:@"address: %@", [self displayIdentifier:self.targetIdentifier.UUIDString ?: @""]]];
    [self.logger write:[NSString stringWithFormat:@"service_uuid: %@", self.targetServiceUUID.UUIDString ?: @""]];
    [self.logger write:[NSString stringWithFormat:@"characteristic_uuid: %@", self.targetCharacteristicUUID.UUIDString ?: @""]];
    [self processDaemonState];
    if (!self.daemonOnce) {
        [NSTimer scheduledTimerWithTimeInterval:self.pollInterval target:self selector:@selector(processDaemonState) userInfo:nil repeats:YES];
    }
}

- (BOOL)acquireDaemonLock {
    if (self.lockFileDescriptor >= 0) { return YES; }
    NSString *dir = [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Application Support/TenonCodexLight/locks"];
    [[NSFileManager defaultManager] createDirectoryAtPath:dir withIntermediateDirectories:YES attributes:@{NSFilePosixPermissions: @0700} error:nil];
    NSString *name = [self lockNameForStateFile:self.stateFilePath device:self.targetIdentifier.UUIDString ?: @""];
    self.lockFilePath = [dir stringByAppendingPathComponent:name];
    int fd = open([self.lockFilePath fileSystemRepresentation], O_RDWR | O_CREAT, 0600);
    if (fd < 0) { return NO; }
    if (flock(fd, LOCK_EX | LOCK_NB) != 0) {
        close(fd);
        return NO;
    }
    ftruncate(fd, 0);
    NSString *pid = [NSString stringWithFormat:@"%d\n", getpid()];
    write(fd, pid.UTF8String, strlen(pid.UTF8String));
    self.lockFileDescriptor = fd;
    return YES;
}

- (NSString *)lockNameForStateFile:(NSString *)stateFile device:(NSString *)device {
    NSString *combined = [NSString stringWithFormat:@"%@-%@", stateFile ?: @"state", device ?: @"device"];
    NSMutableString *safe = [NSMutableString string];
    NSCharacterSet *allowed = [NSCharacterSet alphanumericCharacterSet];
    for (NSUInteger i = 0; i < combined.length; i++) {
        unichar ch = [combined characterAtIndex:i];
        if ([allowed characterIsMember:ch]) {
            [safe appendFormat:@"%C", ch];
        } else {
            [safe appendString:@"_"];
        }
        if (safe.length >= 180) { break; }
    }
    return [NSString stringWithFormat:@"%@.lock", safe];
}

- (void)processDaemonState {
    if (self.writeColor) { return; }

    NSError *error = nil;
    NSString *raw = [NSString stringWithContentsOfFile:self.stateFilePath encoding:NSUTF8StringEncoding error:&error];
    if (error) {
        if (self.daemonOnce) {
            [self.logger write:@"daemon_error: state file not found"];
            [self finish:1];
        }
        return;
    }

    if ([raw lengthOfBytesUsingEncoding:NSUTF8StringEncoding] > 64) {
        [self.logger write:@"invalid_state: too large"];
        if (self.daemonOnce) { [self finish:1]; }
        return;
    }

    NSString *state = [raw stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    NSData *payload = [self payloadForState:state];
    if (!payload) {
        [self.logger write:@"invalid_state: unknown"];
        if (self.daemonOnce) { [self finish:1]; }
        return;
    }

    if ([state isEqualToString:self.lastState]) {
        if (self.daemonOnce) { [self finish:1]; }
        return;
    }

    self.pendingState = state;
    NSData *effectPayload = nil;
    NSString *presetName = nil;
    NSString *effectJson = nil;
    NSInteger actionType = -1;
    if (!self.effectsDisabled && ![state isEqualToString:@"off"]) {
        effectPayload = [self effectPayloadForState:state presetName:&presetName json:&effectJson actionType:&actionType];
    }

    self.pendingFallbackPayload = payload;
    self.pendingEffectWrite = effectPayload != nil;
    self.pendingMode = self.pendingEffectWrite ? @"effect" : @"hsv";
    self.pendingPresetName = presetName ?: ([state isEqualToString:@"off"] ? @"Off" : @"");
    self.effectName = self.pendingEffectWrite ? [self effectNameForActionType:actionType] : nil;
    self.effectActionType = actionType;
    self.effectJson = effectJson;
    self.writeEffect = self.pendingEffectWrite;
    self.writePayload = effectPayload ?: payload;
    self.writeColor = YES;
    [self.logger write:[NSString stringWithFormat:@"state: %@ mode: %@ preset: %@ payload: %@", state, self.pendingMode, self.pendingPresetName ?: @"", [self hexString:self.writePayload]]];
    if (self.effectJson.length > 0) {
        [self.logger write:[NSString stringWithFormat:@"json: %@", self.effectJson]];
    }
    [self startWriteProbe];
}

- (NSData *)payloadForState:(NSString *)state {
    NSInteger h = 0;
    NSInteger s = 0;
    NSInteger v = 0;

    if ([state isEqualToString:@"working"]) {
        h = 197; s = 70; v = 100;
    } else if ([state isEqualToString:@"needs_input"]) {
        h = 288; s = 75; v = 100;
    } else if ([state isEqualToString:@"idle"]) {
        h = 210; s = 11; v = 90;
    } else if ([state isEqualToString:@"error"]) {
        h = 45; s = 100; v = 100;
    } else if ([state isEqualToString:@"off"]) {
        h = 0; s = 0; v = 0;
    } else if ([state isEqualToString:@"restore"]) {
        h = 210; s = 11; v = 90;
    } else {
        return nil;
    }

    unsigned char bytes[] = {
        0x03,
        (unsigned char)((h >> 8) & 0xFF),
        (unsigned char)(h & 0xFF),
        (unsigned char)s,
        (unsigned char)v,
    };
    return [NSData dataWithBytes:bytes length:sizeof(bytes)];
}

- (NSData *)effectPayloadForState:(NSString *)state presetName:(NSString **)presetName json:(NSString **)json actionType:(NSInteger *)actionType {
    NSInteger h0 = 0;
    NSInteger s0 = 0;
    NSInteger v0 = 0;
    NSInteger h1 = 0;
    NSInteger s1 = 0;
    NSInteger v1 = 0;
    NSInteger type = 0;
    NSString *name = nil;

    if ([state isEqualToString:@"idle"] || [state isEqualToString:@"restore"]) {
        name = @"Cloudy"; h0 = 210; s0 = 11; v0 = 90; h1 = 210; s1 = 15; v1 = 70; type = 0;
    } else if ([state isEqualToString:@"working"]) {
        name = @"Aurora"; h0 = 197; s0 = 70; v0 = 100; h1 = 270; s1 = 80; v1 = 100; type = 2;
    } else if ([state isEqualToString:@"needs_input"]) {
        name = @"Lavender Sunset"; h0 = 288; s0 = 75; v0 = 100; h1 = 17; s1 = 85; v1 = 100; type = 3;
    } else if ([state isEqualToString:@"error"]) {
        name = @"Yellow Alert"; h0 = 45; s0 = 100; v0 = 100; h1 = 45; s1 = 100; v1 = 100; type = 1;
    } else {
        return nil;
    }

    NSInteger interval = 1000;
    if ([state isEqualToString:@"needs_input"]) {
        interval = 5000;
    } else if ([state isEqualToString:@"error"]) {
        interval = 300;
    }

    NSString *body = [NSString stringWithFormat:@"{\"action\":{\"interval\":%ld,\"type\":%ld},\"color\":{\"h\":[%ld,%ld],\"s\":[%ld,%ld],\"type\":1,\"v\":[%ld,%ld]}}", (long)interval, (long)type, (long)h0, (long)h1, (long)s0, (long)s1, (long)v0, (long)v1];
    if (presetName) { *presetName = name; }
    if (json) { *json = body; }
    if (actionType) { *actionType = type; }
    return effectPayloadFromJson(body);
}

- (NSString *)effectNameForActionType:(NSInteger)type {
    switch (type) {
        case 0: return @"none";
        case 1: return @"blink";
        case 2: return @"breathe";
        case 3: return @"moving";
        case 4: return @"dancing";
        case 5: return @"rolling";
        default: return @"";
    }
}

- (void)startScan {
    [self.logger write:[NSString stringWithFormat:@"scan_duration: %.1fs", self.duration]];
    [self.logger write:[NSString stringWithFormat:@"services_requested: %@", self.includeServices ? @"true" : @"false"]];
    [self.central scanForPeripheralsWithServices:nil options:@{CBCentralManagerScanOptionAllowDuplicatesKey: @NO}];

    if (!self.didScheduleFinish) {
        self.didScheduleFinish = YES;
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(self.duration * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            [self scanWindowFinished];
        });
    }
}

- (void)startWriteProbe {
    if (!self.targetIdentifier || !self.targetServiceUUID || !self.targetCharacteristicUUID || !self.writePayload) {
        [self.logger write:@"write_error: missing explicit address/service/characteristic/payload"];
        [self finish:2];
        return;
    }

    [self.logger write:[NSString stringWithFormat:@"address: %@", [self displayIdentifier:self.targetIdentifier.UUIDString]]];
    [self.logger write:[NSString stringWithFormat:@"service_uuid: %@", self.targetServiceUUID.UUIDString]];
    [self.logger write:[NSString stringWithFormat:@"characteristic_uuid: %@", self.targetCharacteristicUUID.UUIDString]];
    [self.logger write:[NSString stringWithFormat:@"write_mode: %@", self.writeType == CBCharacteristicWriteWithResponse ? @"response" : @"no-response"]];
    if (self.writeEffect) {
        [self.logger write:[NSString stringWithFormat:@"effect: %@", self.effectName ?: @""]];
        [self.logger write:[NSString stringWithFormat:@"action_type: %ld", (long)self.effectActionType]];
        [self.logger write:[NSString stringWithFormat:@"json: %@", self.effectJson ?: @""]];
    }
    [self.logger write:[NSString stringWithFormat:@"payload: %@", [self hexString:self.writePayload]]];

    NSArray<CBPeripheral *> *known = [self.central retrievePeripheralsWithIdentifiers:@[self.targetIdentifier]];
    if (known.count > 0) {
        self.writePeripheral = known.firstObject;
        self.writePeripheral.delegate = self;
        [self.central connectPeripheral:self.writePeripheral options:nil];
    } else {
        [self.central scanForPeripheralsWithServices:nil options:@{CBCentralManagerScanOptionAllowDuplicatesKey: @NO}];
    }

    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(12 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
        if (self.writeColor) {
            [self.central stopScan];
            if (self.writePeripheral) { [self.central cancelPeripheralConnection:self.writePeripheral]; }
            [self.logger write:@"write_error: timed out before write completed"];
            self.writeColor = NO;
            if ([self fallbackToHSVAfterEffectFailure:@"timeout"]) { return; }
            self.pendingState = nil;
            if (self.daemonMode && !self.daemonOnce) { return; }
            [self finish:2];
        }
    });
}

- (BOOL)fallbackToHSVAfterEffectFailure:(NSString *)reason {
    if (!self.pendingEffectWrite || !self.pendingFallbackPayload || self.cleanupInProgress) {
        return NO;
    }
    [self.logger write:[NSString stringWithFormat:@"fallback: effect failed, using hsv (%@)", reason ?: @"unknown"]];
    self.pendingEffectWrite = NO;
    self.writeEffect = NO;
    self.pendingMode = @"hsv";
    self.writePayload = self.pendingFallbackPayload;
    self.writeColor = YES;
    [self.logger write:[NSString stringWithFormat:@"state: %@ mode: hsv preset: %@ payload: %@", self.pendingState ?: @"", self.pendingPresetName ?: @"", [self hexString:self.writePayload]]];
    [self startWriteProbe];
    return YES;
}

- (NSString *)displayIdentifier:(NSString *)identifier {
    if (self.verboseIdentifiers || identifier.length <= 12) { return identifier ?: @""; }
    NSString *prefix = [identifier substringToIndex:8];
    NSString *suffix = [identifier substringFromIndex:identifier.length - 4];
    return [NSString stringWithFormat:@"%@...%@", prefix, suffix];
}

- (void)centralManager:(CBCentralManager *)central
 didDiscoverPeripheral:(CBPeripheral *)peripheral
     advertisementData:(NSDictionary<NSString *,id> *)advertisementData
                  RSSI:(NSNumber *)RSSI {
    if (self.writeColor) {
        if ([peripheral.identifier isEqual:self.targetIdentifier]) {
            [self.central stopScan];
            self.writePeripheral = peripheral;
            self.writePeripheral.delegate = self;
            [self.central connectPeripheral:peripheral options:nil];
        }
        return;
    }

    PeripheralRecord *record = [PeripheralRecord new];
    record.peripheral = peripheral;
    record.name = peripheral.name ?: advertisementData[CBAdvertisementDataLocalNameKey] ?: @"(unknown)";
    record.rssi = RSSI.integerValue;
    record.advertisedServices = advertisementData[CBAdvertisementDataServiceUUIDsKey] ?: @[];
    record.manufacturerDataPresent = advertisementData[CBAdvertisementDataManufacturerDataKey] != nil;
    NSDictionary *serviceData = advertisementData[CBAdvertisementDataServiceDataKey] ?: @{};
    record.serviceDataUUIDs = [[serviceData allKeys] sortedArrayUsingComparator:^NSComparisonResult(CBUUID *a, CBUUID *b) {
        return [a.UUIDString compare:b.UUIDString];
    }];
    record.discoveredServices = @[];
    record.discoveredCharacteristics = [NSMutableDictionary dictionary];
    self.records[peripheral.identifier] = record;
}

- (void)scanWindowFinished {
    [self.central stopScan];
    if (!self.includeServices) {
        [self printResults];
        [self finish:0];
        return;
    }

    NSArray<PeripheralRecord *> *targets = [self serviceDiscoveryTargets];
    if (targets.count == 0) {
        [self printResults];
        [self finish:0];
        return;
    }

    for (PeripheralRecord *record in targets) {
        record.peripheral.delegate = self;
        [self.pendingServiceDiscovery addObject:record.peripheral.identifier];
        [self.central connectPeripheral:record.peripheral options:nil];
    }

    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(10 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
        [self serviceDiscoveryTimedOut];
    });
}

- (NSArray<PeripheralRecord *> *)serviceDiscoveryTargets {
    NSMutableArray<PeripheralRecord *> *likely = [NSMutableArray array];
    for (PeripheralRecord *record in self.records.allValues) {
        if ([self isLikelyTenon:record]) { [likely addObject:record]; }
    }
    if (likely.count > 0) { return likely; }

    NSArray *sorted = [self.records.allValues sortedArrayUsingComparator:^NSComparisonResult(PeripheralRecord *a, PeripheralRecord *b) {
        return [a.name compare:b.name];
    }];
    NSUInteger count = MIN((NSUInteger)8, sorted.count);
    return [sorted subarrayWithRange:NSMakeRange(0, count)];
}

- (void)centralManager:(CBCentralManager *)central didConnectPeripheral:(CBPeripheral *)peripheral {
    if (self.writeColor) {
        [self.logger write:@"connected: true"];
        [peripheral discoverServices:@[self.targetServiceUUID]];
    } else {
        [peripheral discoverServices:nil];
    }
}

- (void)centralManager:(CBCentralManager *)central didFailToConnectPeripheral:(CBPeripheral *)peripheral error:(NSError *)error {
    if (self.writeColor) {
        [self.logger write:[NSString stringWithFormat:@"write_error: connect failed: %@", error.localizedDescription ?: @"unknown"]];
        self.writeColor = NO;
        if ([self fallbackToHSVAfterEffectFailure:@"connect failed"]) { return; }
        self.pendingState = nil;
        if (self.daemonMode && !self.daemonOnce) { return; }
        [self finish:2];
        return;
    }

    PeripheralRecord *record = self.records[peripheral.identifier];
    record.serviceDiscoveryError = error.localizedDescription ?: @"connect failed";
    [self.pendingServiceDiscovery removeObject:peripheral.identifier];
    [self maybeFinishServiceDiscovery];
}

- (void)peripheral:(CBPeripheral *)peripheral didDiscoverServices:(NSError *)error {
    if (self.writeColor) {
        if (error) {
            [self.logger write:[NSString stringWithFormat:@"write_error: service discovery failed: %@", error.localizedDescription]];
            self.writeColor = NO;
            if ([self fallbackToHSVAfterEffectFailure:@"service discovery failed"]) { return; }
            self.pendingState = nil;
            if (self.daemonMode && !self.daemonOnce) { return; }
            [self finish:2];
            return;
        }
        CBService *target = nil;
        for (CBService *service in peripheral.services ?: @[]) {
            if ([service.UUID isEqual:self.targetServiceUUID]) {
                target = service;
                break;
            }
        }
        if (!target) {
            [self.logger write:@"write_error: target service not found"];
            self.writeColor = NO;
            if ([self fallbackToHSVAfterEffectFailure:@"target service not found"]) { return; }
            self.pendingState = nil;
            if (self.daemonMode && !self.daemonOnce) { return; }
            [self finish:2];
            return;
        }
        [peripheral discoverCharacteristics:@[self.targetCharacteristicUUID] forService:target];
        return;
    }

    PeripheralRecord *record = self.records[peripheral.identifier];
    if (error) {
        record.serviceDiscoveryError = error.localizedDescription;
        [self.central cancelPeripheralConnection:peripheral];
        [self.pendingServiceDiscovery removeObject:peripheral.identifier];
        [self maybeFinishServiceDiscovery];
    } else {
        record.discoveredServices = peripheral.services ?: @[];
        if (record.discoveredServices.count == 0) {
            [self.central cancelPeripheralConnection:peripheral];
            [self.pendingServiceDiscovery removeObject:peripheral.identifier];
            [self maybeFinishServiceDiscovery];
            return;
        }
        for (CBService *service in record.discoveredServices) {
            NSString *key = [self characteristicDiscoveryKeyForPeripheral:peripheral service:service];
            [self.pendingCharacteristicDiscovery addObject:key];
            [peripheral discoverCharacteristics:nil forService:service];
        }
    }
}

- (void)peripheral:(CBPeripheral *)peripheral didDiscoverCharacteristicsForService:(CBService *)service error:(NSError *)error {
    if (self.writeColor) {
        if (error) {
            [self.logger write:[NSString stringWithFormat:@"write_error: characteristic discovery failed: %@", error.localizedDescription]];
            self.writeColor = NO;
            if ([self fallbackToHSVAfterEffectFailure:@"characteristic discovery failed"]) { return; }
            self.pendingState = nil;
            if (self.daemonMode && !self.daemonOnce) { return; }
            [self finish:2];
            return;
        }
        CBCharacteristic *target = nil;
        for (CBCharacteristic *characteristic in service.characteristics ?: @[]) {
            if ([characteristic.UUID isEqual:self.targetCharacteristicUUID]) {
                target = characteristic;
                break;
            }
        }
        if (!target) {
            [self.logger write:@"write_error: target characteristic not found"];
            self.writeColor = NO;
            if ([self fallbackToHSVAfterEffectFailure:@"target characteristic not found"]) { return; }
            self.pendingState = nil;
            if (self.daemonMode && !self.daemonOnce) { return; }
            [self finish:2];
            return;
        }
        [peripheral writeValue:self.writePayload forCharacteristic:target type:self.writeType];
        if (self.writeType == CBCharacteristicWriteWithoutResponse) {
            [self.logger write:@"write: ok"];
            [self.central cancelPeripheralConnection:peripheral];
            self.lastState = self.pendingState;
            self.pendingEffectWrite = NO;
            self.writeEffect = NO;
            self.pendingFallbackPayload = nil;
            self.pendingMode = nil;
            self.pendingPresetName = nil;
            self.pendingState = nil;
            self.writeColor = NO;
            if (self.cleanupInProgress) { [self finishWithoutCleanup:self.pendingExitCode]; return; }
            if (self.daemonMode && !self.daemonOnce) { return; }
            [self finish:0];
        }
        return;
    }

    PeripheralRecord *record = self.records[peripheral.identifier];
    NSString *key = [self characteristicDiscoveryKeyForPeripheral:peripheral service:service];
    [self.pendingCharacteristicDiscovery removeObject:key];

    if (error) {
        record.serviceDiscoveryError = error.localizedDescription;
    } else {
        record.discoveredCharacteristics[service.UUID.UUIDString] = service.characteristics ?: @[];
    }

    if (![self hasPendingCharacteristicsForPeripheral:peripheral]) {
        [self.central cancelPeripheralConnection:peripheral];
        [self.pendingServiceDiscovery removeObject:peripheral.identifier];
        [self maybeFinishServiceDiscovery];
    }
}

- (void)peripheral:(CBPeripheral *)peripheral didWriteValueForCharacteristic:(CBCharacteristic *)characteristic error:(NSError *)error {
    if (!self.writeColor) { return; }
    if (error) {
        [self.logger write:[NSString stringWithFormat:@"write_error: %@", error.localizedDescription]];
        [self.central cancelPeripheralConnection:peripheral];
        self.writeColor = NO;
        if ([self fallbackToHSVAfterEffectFailure:@"write error"]) { return; }
        self.pendingState = nil;
        if (self.daemonMode && !self.daemonOnce) { return; }
        [self finish:2];
        return;
    }
    [self.logger write:@"write: ok"];
    [self.central cancelPeripheralConnection:peripheral];
    self.lastState = self.pendingState;
    self.pendingEffectWrite = NO;
    self.writeEffect = NO;
    self.pendingFallbackPayload = nil;
    self.pendingMode = nil;
    self.pendingPresetName = nil;
    self.pendingState = nil;
    self.writeColor = NO;
    if (self.cleanupInProgress) { [self finishWithoutCleanup:self.pendingExitCode]; return; }
    if (self.daemonMode && !self.daemonOnce) { return; }
    [self finish:0];
}

- (void)serviceDiscoveryTimedOut {
    for (NSUUID *identifier in self.pendingServiceDiscovery) {
        CBPeripheral *peripheral = self.records[identifier].peripheral;
        if (peripheral) { [self.central cancelPeripheralConnection:peripheral]; }
    }
    [self.pendingServiceDiscovery removeAllObjects];
    [self.pendingCharacteristicDiscovery removeAllObjects];
    [self printResults];
    [self finish:0];
}

- (NSString *)characteristicDiscoveryKeyForPeripheral:(CBPeripheral *)peripheral service:(CBService *)service {
    return [NSString stringWithFormat:@"%@|%@", peripheral.identifier.UUIDString, service.UUID.UUIDString];
}

- (BOOL)hasPendingCharacteristicsForPeripheral:(CBPeripheral *)peripheral {
    NSString *prefix = [peripheral.identifier.UUIDString stringByAppendingString:@"|"];
    for (NSString *key in self.pendingCharacteristicDiscovery) {
        if ([key hasPrefix:prefix]) { return YES; }
    }
    return NO;
}

- (void)maybeFinishServiceDiscovery {
    if (self.pendingServiceDiscovery.count == 0) {
        [self printResults];
        [self finish:0];
    }
}

- (BOOL)isLikelyTenon:(PeripheralRecord *)record {
    NSString *lower = record.name.lowercaseString;
    if ([lower containsString:@"tenon"] || [lower containsString:@"beflo"] || [lower isEqualToString:@"onoo"]) {
        return YES;
    }

    NSSet<NSString *> *hints = [NSSet setWithArray:@[
        @"4D543739-3333-2E4F-4E4F-4F2E4445534B",
        @"4D543739-3333-2E4F-4E4F-4F2E434C4544",
        @"4D543739-3333-2E4F-4E4F-4F2E434C5257",
    ]];
    for (CBUUID *uuid in record.advertisedServices) {
        if ([hints containsObject:uuid.UUIDString.uppercaseString]) {
            return YES;
        }
    }
    return NO;
}

- (void)printResults {
    NSArray<PeripheralRecord *> *sorted = [self.records.allValues sortedArrayUsingComparator:^NSComparisonResult(PeripheralRecord *a, PeripheralRecord *b) {
        BOOL aLikely = [self isLikelyTenon:a];
        BOOL bLikely = [self isLikelyTenon:b];
        if (aLikely != bLikely) { return aLikely ? NSOrderedAscending : NSOrderedDescending; }
        return [a.name compare:b.name];
    }];

    [self.logger write:[NSString stringWithFormat:@"devices_found: %lu", (unsigned long)sorted.count]];
    NSUInteger index = 1;
    for (PeripheralRecord *record in sorted) {
        NSString *marker = [self isLikelyTenon:record] ? @" likely_tenon" : @"";
        [self.logger write:[NSString stringWithFormat:@"%lu. %@ [%@] rssi=%ld%@", (unsigned long)index, record.name, [self displayIdentifier:record.peripheral.identifier.UUIDString], (long)record.rssi, marker]];

        if (self.verbose || [self isLikelyTenon:record]) {
            if (record.advertisedServices.count > 0) {
                [self.logger write:@"   advertised_services:"];
                for (CBUUID *uuid in record.advertisedServices) {
                    [self.logger write:[NSString stringWithFormat:@"   - %@", uuid.UUIDString]];
                }
            }
            if (record.manufacturerDataPresent) {
                [self.logger write:@"   manufacturer_data: present"];
            }
            if (record.serviceDataUUIDs.count > 0) {
                [self.logger write:@"   service_data:"];
                for (CBUUID *uuid in record.serviceDataUUIDs) {
                    [self.logger write:[NSString stringWithFormat:@"   - %@", uuid.UUIDString]];
                }
            }
        }

        if (self.includeServices) {
            if (record.discoveredServices.count > 0) {
                [self.logger write:@"   services:"];
                for (CBService *service in record.discoveredServices) {
                    [self.logger write:[NSString stringWithFormat:@"   - %@", service.UUID.UUIDString]];
                    NSArray<CBCharacteristic *> *characteristics = record.discoveredCharacteristics[service.UUID.UUIDString] ?: @[];
                    for (CBCharacteristic *characteristic in characteristics) {
                        [self.logger write:[NSString stringWithFormat:@"     - %@ (%@)", characteristic.UUID.UUIDString, [self propertiesString:characteristic.properties]]];
                    }
                }
            }
            if (record.serviceDiscoveryError.length > 0) {
                [self.logger write:[NSString stringWithFormat:@"   service_discovery_error: %@", record.serviceDiscoveryError]];
            }
        }
        index += 1;
    }
}

- (void)finish:(int)exitCode {
    if (self.daemonMode && !self.daemonOnce && !self.cleanupInProgress) {
        self.cleanupInProgress = YES;
        self.pendingExitCode = exitCode;
        self.pendingState = @"idle";
        self.writePayload = [self payloadForState:@"idle"];
        self.pendingEffectWrite = NO;
        self.writeEffect = NO;
        self.pendingFallbackPayload = nil;
        self.pendingMode = @"hsv";
        self.pendingPresetName = @"Cloudy";
        self.writeColor = YES;
        [self.logger write:[NSString stringWithFormat:@"daemon: cleanup idle mode: hsv payload: %@", [self hexString:self.writePayload]]];
        [self startWriteProbe];
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(6 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            if (self.cleanupInProgress) {
                [self.logger write:@"daemon: cleanup timeout"];
                [self finishWithoutCleanup:self.pendingExitCode];
            }
        });
        return;
    }
    [self finishWithoutCleanup:exitCode];
}

- (void)finishWithoutCleanup:(int)exitCode {
    [self releaseDaemonLock];
    fflush(stdout);
    dispatch_async(dispatch_get_main_queue(), ^{
        exit(exitCode);
    });
}

- (void)releaseDaemonLock {
    if (self.lockFileDescriptor >= 0) {
        flock(self.lockFileDescriptor, LOCK_UN);
        close(self.lockFileDescriptor);
        self.lockFileDescriptor = -1;
    }
}

- (NSString *)propertiesString:(CBCharacteristicProperties)properties {
    NSMutableArray<NSString *> *values = [NSMutableArray array];
    if (properties & CBCharacteristicPropertyBroadcast) { [values addObject:@"broadcast"]; }
    if (properties & CBCharacteristicPropertyRead) { [values addObject:@"read"]; }
    if (properties & CBCharacteristicPropertyWriteWithoutResponse) { [values addObject:@"write-without-response"]; }
    if (properties & CBCharacteristicPropertyWrite) { [values addObject:@"write"]; }
    if (properties & CBCharacteristicPropertyNotify) { [values addObject:@"notify"]; }
    if (properties & CBCharacteristicPropertyIndicate) { [values addObject:@"indicate"]; }
    if (properties & CBCharacteristicPropertyAuthenticatedSignedWrites) { [values addObject:@"authenticated-signed-writes"]; }
    if (properties & CBCharacteristicPropertyExtendedProperties) { [values addObject:@"extended-properties"]; }
    if (properties & CBCharacteristicPropertyNotifyEncryptionRequired) { [values addObject:@"notify-encryption-required"]; }
    if (properties & CBCharacteristicPropertyIndicateEncryptionRequired) { [values addObject:@"indicate-encryption-required"]; }
    if (values.count == 0) { return @"none"; }
    return [values componentsJoinedByString:@", "];
}

- (NSString *)hexString:(NSData *)data {
    const unsigned char *bytes = data.bytes;
    NSMutableArray<NSString *> *parts = [NSMutableArray array];
    for (NSUInteger i = 0; i < data.length; i++) {
        [parts addObject:[NSString stringWithFormat:@"%02X", bytes[i]]];
    }
    return [parts componentsJoinedByString:@" "];
}
@end

static NSTimeInterval durationFromArguments(NSArray<NSString *> *arguments) {
    NSUInteger index = [arguments indexOfObject:@"--duration"];
    if (index != NSNotFound && index + 1 < arguments.count) {
        return arguments[index + 1].doubleValue;
    }
    return 8;
}

static NSString *argumentValue(NSArray<NSString *> *arguments, NSString *name) {
    NSUInteger index = [arguments indexOfObject:name];
    if (index != NSNotFound && index + 1 < arguments.count) {
        return arguments[index + 1];
    }
    return nil;
}

static NSString *defaultStateFilePath(void) {
    return [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Application Support/TenonCodexLight/state"];
}

static NSData *hsvPayloadFromArguments(NSArray<NSString *> *arguments) {
    NSInteger h = [argumentValue(arguments, @"--h") integerValue];
    NSInteger s = [argumentValue(arguments, @"--s") integerValue];
    NSInteger v = [argumentValue(arguments, @"--v") integerValue];
    unsigned char bytes[] = {
        0x03,
        (unsigned char)((h >> 8) & 0xFF),
        (unsigned char)(h & 0xFF),
        (unsigned char)s,
        (unsigned char)v,
    };
    return [NSData dataWithBytes:bytes length:sizeof(bytes)];
}

static NSInteger actionTypeForEffect(NSString *effect) {
    NSDictionary<NSString *, NSNumber *> *types = @{
        @"none": @0,
        @"blink": @1,
        @"breathe": @2,
        @"moving": @3,
        @"dancing": @4,
        @"rolling": @5,
    };
    NSNumber *value = types[effect ?: @""];
    return value ? value.integerValue : -1;
}

static NSString *effectJsonFromArguments(NSArray<NSString *> *arguments, NSInteger actionType) {
    NSInteger h = argumentValue(arguments, @"--h") ? [argumentValue(arguments, @"--h") integerValue] : 210;
    NSInteger s = argumentValue(arguments, @"--s") ? [argumentValue(arguments, @"--s") integerValue] : 80;
    NSInteger v = argumentValue(arguments, @"--v") ? [argumentValue(arguments, @"--v") integerValue] : 50;
    NSInteger interval = argumentValue(arguments, @"--interval-ms") ? [argumentValue(arguments, @"--interval-ms") integerValue] : 1000;
    return [NSString stringWithFormat:@"{\"action\":{\"interval\":%ld,\"type\":%ld},\"color\":{\"h\":[%ld,0],\"s\":[%ld,0],\"type\":0,\"v\":[%ld,0]}}", (long)interval, (long)actionType, (long)h, (long)s, (long)v];
}

static BOOL effectArgumentsHaveSafeRanges(NSArray<NSString *> *arguments) {
    NSInteger h = argumentValue(arguments, @"--h") ? [argumentValue(arguments, @"--h") integerValue] : 210;
    NSInteger s = argumentValue(arguments, @"--s") ? [argumentValue(arguments, @"--s") integerValue] : 80;
    NSInteger v = argumentValue(arguments, @"--v") ? [argumentValue(arguments, @"--v") integerValue] : 50;
    NSInteger interval = argumentValue(arguments, @"--interval-ms") ? [argumentValue(arguments, @"--interval-ms") integerValue] : 1000;
    return h >= 0 && h <= 359 && s >= 0 && s <= 100 && v >= 0 && v <= 100 && interval >= 0 && interval <= 60000;
}

static NSData *effectPayloadFromJson(NSString *json) {
    NSMutableData *payload = [NSMutableData dataWithBytes:(unsigned char[]){0x05} length:1];
    [payload appendData:[json dataUsingEncoding:NSUTF8StringEncoding]];
    return payload;
}

static BOOL isAllowedTenonService(CBUUID *uuid) {
    return [uuid.UUIDString.uppercaseString isEqualToString:@"4D543739-3333-2E4F-4E4F-4F2E4445534B"];
}

static BOOL isAllowedLedCharacteristic(CBUUID *uuid) {
    return [uuid.UUIDString.uppercaseString isEqualToString:@"4D543739-3333-2E4F-4E4F-4F2E434C4544"];
}

@interface AppDelegate : NSObject <NSApplicationDelegate>
@property(nonatomic, strong) ScanDelegate *scanDelegate;
@property(nonatomic, strong) dispatch_source_t sigintSource;
@property(nonatomic, strong) dispatch_source_t sigtermSource;
@end

@implementation AppDelegate
- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    (void)notification;
    NSArray<NSString *> *arguments = [[NSProcessInfo processInfo] arguments];
    BOOL includeServices = [arguments containsObject:@"--services"];
    BOOL verbose = [arguments containsObject:@"--verbose"];
    Logger *logger = [Logger new];
    [logger write:@"app: launched"];
    self.scanDelegate = [[ScanDelegate alloc] initWithDuration:durationFromArguments(arguments) includeServices:includeServices verbose:verbose logger:logger];
    self.scanDelegate.verboseIdentifiers = [arguments containsObject:@"--verbose-identifiers"];
    if ([arguments containsObject:@"--write-color"]) {
        self.scanDelegate.writeColor = YES;
        self.scanDelegate.targetIdentifier = [[NSUUID alloc] initWithUUIDString:argumentValue(arguments, @"--address") ?: @""];
        self.scanDelegate.targetServiceUUID = [CBUUID UUIDWithString:argumentValue(arguments, @"--service-uuid") ?: @""];
        self.scanDelegate.targetCharacteristicUUID = [CBUUID UUIDWithString:argumentValue(arguments, @"--characteristic-uuid") ?: @""];
        self.scanDelegate.writePayload = hsvPayloadFromArguments(arguments);
        NSString *writeMode = argumentValue(arguments, @"--write-mode") ?: @"response";
        self.scanDelegate.writeType = [writeMode isEqualToString:@"no-response"] ? CBCharacteristicWriteWithoutResponse : CBCharacteristicWriteWithResponse;
    } else if ([arguments containsObject:@"--write-effect"]) {
        self.scanDelegate.writeColor = YES;
        self.scanDelegate.writeEffect = YES;
        self.scanDelegate.targetIdentifier = [[NSUUID alloc] initWithUUIDString:argumentValue(arguments, @"--address") ?: @""];
        self.scanDelegate.targetServiceUUID = [CBUUID UUIDWithString:argumentValue(arguments, @"--service-uuid") ?: @""];
        self.scanDelegate.targetCharacteristicUUID = [CBUUID UUIDWithString:argumentValue(arguments, @"--characteristic-uuid") ?: @""];
        NSString *writeMode = argumentValue(arguments, @"--write-mode") ?: @"response";
        self.scanDelegate.writeType = [writeMode isEqualToString:@"response"] ? CBCharacteristicWriteWithResponse : CBCharacteristicWriteWithoutResponse;
        self.scanDelegate.effectName = argumentValue(arguments, @"--effect") ?: @"";
        self.scanDelegate.effectActionType = actionTypeForEffect(self.scanDelegate.effectName);
        self.scanDelegate.effectJson = effectJsonFromArguments(arguments, self.scanDelegate.effectActionType);
        self.scanDelegate.writePayload = effectPayloadFromJson(self.scanDelegate.effectJson);
        if (![arguments containsObject:@"--i-understand-this-is-experimental"]) {
            [logger write:@"write_error: real effect writes require --i-understand-this-is-experimental"];
            exit(2);
        }
        if (self.scanDelegate.writeType != CBCharacteristicWriteWithResponse) {
            [logger write:@"write_error: effect writes require --write-mode response"];
            exit(2);
        }
        if (self.scanDelegate.effectActionType < 0) {
            [logger write:@"write_error: unsupported effect"];
            exit(2);
        }
        if (!effectArgumentsHaveSafeRanges(arguments)) {
            [logger write:@"write_error: effect HSV/interval values out of range"];
            exit(2);
        }
        if (!isAllowedTenonService(self.scanDelegate.targetServiceUUID)) {
            [logger write:@"write_error: service UUID is not allowlisted for Tenon effects"];
            exit(2);
        }
        if (!isAllowedLedCharacteristic(self.scanDelegate.targetCharacteristicUUID)) {
            [logger write:@"write_error: characteristic UUID is not allowlisted for Tenon effects"];
            exit(2);
        }
    } else if ([arguments containsObject:@"--daemon"]) {
        self.scanDelegate.daemonMode = YES;
        self.scanDelegate.daemonOnce = [arguments containsObject:@"--once"];
        self.scanDelegate.targetIdentifier = [[NSUUID alloc] initWithUUIDString:argumentValue(arguments, @"--address") ?: @""];
        self.scanDelegate.targetServiceUUID = [CBUUID UUIDWithString:argumentValue(arguments, @"--service-uuid") ?: @"4D543739-3333-2E4F-4E4F-4F2E4445534B"];
        self.scanDelegate.targetCharacteristicUUID = [CBUUID UUIDWithString:argumentValue(arguments, @"--characteristic-uuid") ?: @"4D543739-3333-2E4F-4E4F-4F2E434C4544"];
        self.scanDelegate.writeType = CBCharacteristicWriteWithResponse;
        self.scanDelegate.stateFilePath = argumentValue(arguments, @"--state-file") ?: defaultStateFilePath();
        self.scanDelegate.effectsDisabled = [arguments containsObject:@"--disable-effects"];
        NSString *pollInterval = argumentValue(arguments, @"--poll-interval");
        self.scanDelegate.pollInterval = pollInterval ? pollInterval.doubleValue : 0.25;
        if (![self.scanDelegate acquireDaemonLock]) {
            [logger write:@"daemon_error: another daemon is already running for this state file and device"];
            exit(1);
        }
    }
    [logger write:[NSString stringWithFormat:@"mode: %@", self.scanDelegate.daemonMode ? @"daemon" : (self.scanDelegate.writeEffect ? @"write-effect" : (self.scanDelegate.writeColor ? @"write-color" : @"scan"))]];
    [self installSignalHandlers];
    [self.scanDelegate start];
}

- (void)installSignalHandlers {
    signal(SIGINT, SIG_IGN);
    signal(SIGTERM, SIG_IGN);
    self.sigintSource = dispatch_source_create(DISPATCH_SOURCE_TYPE_SIGNAL, SIGINT, 0, dispatch_get_main_queue());
    dispatch_source_set_event_handler(self.sigintSource, ^{
        [self.scanDelegate.logger write:@"daemon: received SIGINT"];
        [self.scanDelegate finish:0];
    });
    dispatch_resume(self.sigintSource);

    self.sigtermSource = dispatch_source_create(DISPATCH_SOURCE_TYPE_SIGNAL, SIGTERM, 0, dispatch_get_main_queue());
    dispatch_source_set_event_handler(self.sigtermSource, ^{
        [self.scanDelegate.logger write:@"daemon: received SIGTERM"];
        [self.scanDelegate finish:0];
    });
    dispatch_resume(self.sigtermSource);
}

- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender {
    (void)sender;
    [self.scanDelegate finish:0];
    return NSTerminateCancel;
}
@end

int main(int argc, const char * argv[]) {
    (void)argc;
    (void)argv;
    @autoreleasepool {
        NSApplication *application = [NSApplication sharedApplication];
        application.activationPolicy = NSApplicationActivationPolicyAccessory;
        AppDelegate *delegate = [AppDelegate new];
        application.delegate = delegate;
        [application run];
    }
    return 0;
}
