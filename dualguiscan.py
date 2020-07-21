#!/usr/bin/python3
from PyQt5.QtWidgets import  *
from PyQt5.QtGui import QDoubleValidator, QPixmap
from PyQt5.QtCore import *
import sys
import glob
import os
import time
import subprocess
import traceback
import paho.mqtt.client as mqtt

mqtthost = "pikassa.space.hack42.nl"

class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(str)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.kwargs['progress_callback'] = self.signals.progress

    @pyqtSlot()
    def run(self):
        try:
           result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
                        self.signals.result.emit(result)  # Return the result of the processing
        finally:
                        self.signals.finished.emit()  # Done
class Scan(QWidget):
    files=[]
    Papersizes= {
            'fullsize' : [ "Fullsize" , 221.967, 296.972 ],
            'letter': [ "Letter" , 215.9, 279.4 ],
            'a4'    :  [ "A4", 210.0, 297.3 ],
            'a5'     : [ "A5", 148.0, 210.0 ],
            'almosta5':[ "Bijna A5", 133.0, 210.0 ],
            'b5'     : [ "B5", 173.0, 246.0 ],
            'halfletter' : [ "Half Letter", 177.0, 228.0 ],
            'ibmrt' :     [ "IBM-RT", 217.0, 217.0 ],
            'cdbooklet':   [ "CD Booklet", 120.0, 240.0 ],
            'ibmrt-front' :[ "IBM-RT Voorpagina", 230.0, 217.0 ],
            }

    def __init__(self,scanner):
        super().__init__()
        self.initUI(scanner)
        
    def dirselclick(self):
        dirbrowser = QFileDialog(self, "Select Directory","/home/museum/scans/" if self.directory=="Selecteer ..." else self.directory)
        dirbrowser.setFileMode(QFileDialog.DirectoryOnly)
        if dirbrowser.exec_() == QDialog.Accepted:
            self.directory=dirbrowser.selectedFiles()[0]
        self.dirsel.setText(self.directory.replace("/home/museum/scans/","").replace("/media/museum/INTENSO/scans/","").replace("/media/museum/INTENSO1/scans/",""))
        self.enablescanbutton()

    def setpage(self,progress_callback):
        while True:
            files=glob.glob(self.directory+"/page-*.tiff")
            files.sort()
            if self.files != files: 
                self.page.setText(str(int(files[-1].rstrip('.tiff')[-4:])+1 if len(files) else 1))
                if len(files):
                    os.system("convert -resize x480 '"+files[-1]+"' /run/user/1000/"+self.scanner+".png")
                    self.image.setPixmap(QPixmap("/run/user/1000/"+self.scanner+".png"))
                self.files=files
            time.sleep(1)

    def echtscannensingle(self,progress_callback):
        os.chdir(self.directory)
        files=glob.glob(self.directory+"/page-*.tiff")
        files.sort()
        startimage=str(int(files[-1].rstrip('.tiff')[-4:])+1 if len(files) else 1)
        cmd=["scanimage","-d",self.dev,"--format","tiff",
            "--batch=page-"+'%04d'+".tiff","--batch-start="+startimage,"--source",
            'Flatbed',
            "--mode","Color",
            "--resolution=600",
            "-x","221.967",
            "-y","296.972"]
        print( " ".join(cmd))

        popen = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
        for stderr_line in iter(popen.stderr.readline, ""):
            progress_callback.emit(stderr_line.rstrip())
        popen.stderr.close()
        client = mqtt.Client()
        client.connect(mqtthost, 1883)
        client.publish('hack42bar/output/session/main/sound','win31.mp3')
        return_code = popen.wait()

    def echtscannen(self,progress_callback):
        os.chdir(self.directory)
        files=glob.glob(self.directory+"/page-*.tiff")
        files.sort()
        startimage=str(int(files[-1].rstrip('.tiff')[-4:])+1 if len(files) else 1)
        cmd=["scanimage","-d",self.dev,"--format","tiff",
            "--batch=page-"+'%04d'+".tiff","--batch-start="+startimage,"--source",
            'ADF Duplex',
            "--mode","Color",
            "--resolution=600",
            "--page-width",self.papersizex.text(),
            "--page-height",self.papersizey.text(),
            "-x",self.papersizex.text(),
            "-y",self.papersizey.text()]
        client = mqtt.Client()
        client.connect(mqtthost, 1883)
        client.publish('hack42bar/output/session/main/sound','oxp.wav')

        popen = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
        for stderr_line in iter(popen.stderr.readline, ""):
            progress_callback.emit(stderr_line.rstrip())
        popen.stderr.close()
        client = mqtt.Client()
        client.connect(mqtthost, 1883)
        client.publish('hack42bar/output/session/main/sound','win31.mp3')
        return_code = popen.wait()

    def thread_complete(self):
        self.scanning = 0
        self.scanb.setStyleSheet("background-color: green; color: white;")

    def progress_fn(self,stdout_line):
        self.outputbox.appendPlainText(stdout_line)

    def singlescan(self):
        if self.enablescanbutton != 0:
            self.scanning = 1
            self.scanb.setStyleSheet("background-color: red")
            worker = Worker(self.echtscannensingle)
            worker.signals.finished.connect(self.thread_complete)
            worker.signals.progress.connect(self.progress_fn)
            self.threadpool.start(worker)

    def gascannen(self):
        if self.enablescanbutton != 0:
            self.scanning = 1
            self.scanb.setStyleSheet("background-color: red")
            worker = Worker(self.echtscannen)
            worker.signals.finished.connect(self.thread_complete)
            worker.signals.progress.connect(self.progress_fn)
            self.threadpool.start(worker)

    def enablescanbutton(self):
        if self.directory == 'Selecteer ...': return(0)
        try:
            if float(self.papersizex.text()) <= 0: return(0)
            if float(self.papersizey.text()) <= 0: return(0)
        except:
            return(0)
        if self.scanning != 0: return(2)
        self.scanb.setStyleSheet("background-color: green; color: white;")
        return(1)

    def paperselchanged(self):
        for x in self.Papersizes:
            if self.Papersizes[x][0] == self.papersel.currentText():
                self.papersizex.setText(str(self.Papersizes[x][1]))
                self.papersizey.setText(str(self.Papersizes[x][2]))
        self.enablescanbutton()
        
    def initUI(self,scanner):
        self.scanner=scanner
        self.scanning=0
        scanners= { "linkslinks": "fujitsu:fi-6230dj:3261",
                "linksrechts": "fujitsu:fi-6240dj:5462",
                "rechtslinks": "fujitsu:fi-6230dj:3665",
                "rechtsrechts": "fujitsu:fi-6230dj:11082"
                  }
        self.dev=scanners[self.scanner]
        positions= { "linkslinks": [0,0], 
                     "linksrechts": [160,20],
                     "rechtslinks": [320,20],
                     "rechtsrechts": [640,20] 
                   }
        self.left=positions[self.scanner][0]
        self.top=positions[self.scanner][1]
        self.threadpool = QThreadPool()
        self.directory='Selecteer ...'
        lbl1 = QLabel('Huidige opslagplek:', self)
        lbl1.move(15, 10)
        lbl2 = QLabel('Scanner:', self)
        lbl2.move(15, 40)
        lbl3 = QLabel('Papier grootte:', self)
        lbl3.move(15, 70)        
        self.dirsel = QPushButton(self.directory,self)
        self.dirsel.move(150,5)
        self.dirsel.resize(440,25)
        self.dirsel.clicked.connect(self.dirselclick)
        self.papersel = QComboBox(self)
        self.papersel.addItem("Selecteer ...")
        for x in self.Papersizes:
            self.papersel.addItem(self.Papersizes[x][0])
        self.papersel.move(150,65)
        self.papersel.currentIndexChanged.connect(self.paperselchanged)
        lbl4 = QLabel('Breedte (mm)', self)
        lbl4.move(350, 70)        
        lbl5 = QLabel('Hoogte (mm)', self)
        lbl5.move(450, 70)        
        lbl6 = QLabel(self.scanner, self)
        lbl6.move(150, 40)
        lbl7 = QLabel('Pagina:', self)
        lbl7.move(15, 100)        
        self.page = QLabel('1', self)
        self.page.move(150, 100)        
        self.page.resize(80,20)
        self.papersizex=QLineEdit(self)
        self.papersizex.setValidator(QDoubleValidator(0.001,221.967,3))
        self.papersizex.setMaxLength(7)
        self.papersizex.resize(80,25)
        self.papersizex.move(350,95)
        self.papersizey=QLineEdit(self)
        self.papersizey.setValidator(QDoubleValidator(0.001,296.972,3))
        self.papersizey.setMaxLength(7)
        self.papersizey.resize(80,25)
        self.papersizey.move(450,95)
        self.single = QPushButton("Flatbed",self)
        self.single.move(460,40)
        self.single.resize(90,30)
        self.single.clicked.connect(self.singlescan)
        self.scanb = QPushButton("SCAN SCAN SCAN SCAN SCAN SCAN SCAN SCAN SCAN",self)
        self.scanb.move(80,140)
        self.scanb.resize(440,40)
        self.scanb.clicked.connect(self.gascannen)
        self.outputbox=QPlainTextEdit(self)
        self.outputbox.resize(620,200)
        self.outputbox.move(10,190)
        self.outputbox.setEnabled(False)
        self.image = QLabel("", self)
        self.image.move(10, 410)
        self.image.resize(620,480)
        self.image.setStyleSheet("background-color: white")
        self.image.setAlignment(Qt.AlignCenter)
        self.setGeometry(self.left, self.top, 640, 900)
        self.setWindowTitle('Hack42 Scanner: '+self.scanner)    
        self.show()
        worker = Worker(self.setpage)
        worker.signals.finished.connect(self.thread_complete)
        worker.signals.progress.connect(self.progress_fn)
        self.threadpool.start(worker)
        
if __name__ == '__main__':
    app = QApplication(sys.argv[2:])
    scan = Scan("linkslinks")
    scan = Scan("rechtslinks")
    scan = Scan("linksrechts")
    scan = Scan("rechtsrechts")
    sys.exit(app.exec_())
