export namespace main {
	
	export class Counts {
	    total: number;
	    completed: number;
	    inProgress: number;
	    failed: number;
	
	    static createFrom(source: any = {}) {
	        return new Counts(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.total = source["total"];
	        this.completed = source["completed"];
	        this.inProgress = source["inProgress"];
	        this.failed = source["failed"];
	    }
	}
	export class TransferRecord {
	    id: string;
	    fileName: string;
	    direction: string;
	    status: string;
	    peer: string;
	    bytesDone: number;
	    bytesTotal: number;
	    startedAt: number;
	    endedAt: number;
	    error: string;
	
	    static createFrom(source: any = {}) {
	        return new TransferRecord(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.id = source["id"];
	        this.fileName = source["fileName"];
	        this.direction = source["direction"];
	        this.status = source["status"];
	        this.peer = source["peer"];
	        this.bytesDone = source["bytesDone"];
	        this.bytesTotal = source["bytesTotal"];
	        this.startedAt = source["startedAt"];
	        this.endedAt = source["endedAt"];
	        this.error = source["error"];
	    }
	}
	export class AppState {
	    rootDirectory: string;
	    rootHistory: string[];
	    listenIP: string;
	    serverIP: string;
	    port: number;
	    serverStatus: string;
	    transfers: TransferRecord[];
	    clientTransfer?: TransferRecord;
	    counts: Counts;
	
	    static createFrom(source: any = {}) {
	        return new AppState(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.rootDirectory = source["rootDirectory"];
	        this.rootHistory = source["rootHistory"];
	        this.listenIP = source["listenIP"];
	        this.serverIP = source["serverIP"];
	        this.port = source["port"];
	        this.serverStatus = source["serverStatus"];
	        this.transfers = this.convertValues(source["transfers"], TransferRecord);
	        this.clientTransfer = this.convertValues(source["clientTransfer"], TransferRecord);
	        this.counts = this.convertValues(source["counts"], Counts);
	    }
	
		convertValues(a: any, classs: any, asMap: boolean = false): any {
		    if (!a) {
		        return a;
		    }
		    if (a.slice && a.map) {
		        return (a as any[]).map(elem => this.convertValues(elem, classs));
		    } else if ("object" === typeof a) {
		        if (asMap) {
		            for (const key of Object.keys(a)) {
		                a[key] = new classs(a[key]);
		            }
		            return a;
		        }
		        return new classs(a);
		    }
		    return a;
		}
	}
	export class ClientTransferRequest {
	    action: string;
	    host: string;
	    port: number;
	    localFile: string;
	    remoteFile: string;
	
	    static createFrom(source: any = {}) {
	        return new ClientTransferRequest(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.action = source["action"];
	        this.host = source["host"];
	        this.port = source["port"];
	        this.localFile = source["localFile"];
	        this.remoteFile = source["remoteFile"];
	    }
	}
	

}

