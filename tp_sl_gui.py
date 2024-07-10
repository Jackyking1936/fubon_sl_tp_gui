import sys
import pickle
import json
from pathlib import Path

from fubon_neo.sdk import FubonSDK, Order
from fubon_neo.constant import TimeInForce, OrderType, PriceType, MarketType, BSAction

from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QLineEdit, QGridLayout, QVBoxLayout, QHeaderView, QMessageBox, QTableWidget, QTableWidgetItem, QPlainTextEdit, QFileDialog, QSizePolicy
from PySide6.QtGui import QTextCursor, QIcon, QColor
from PySide6.QtCore import Qt, Signal, QObject, QMutex
from threading import Timer

class LoginForm(QWidget):
    def __init__(self):
        super().__init__()
        my_icon = QIcon()
        my_icon.addFile('inventory.png')

        self.setWindowIcon(my_icon)
        self.setWindowTitle('新一代API_登入')
        self.resize(500, 200)
        
        layout_all = QVBoxLayout()

        label_warning = QLabel('本範例僅供教學參考，使用前請先了解相關內容')
        layout_all.addWidget(label_warning)

        layout = QGridLayout()

        label_your_id = QLabel('Your ID:')
        self.lineEdit_id = QLineEdit()
        self.lineEdit_id.setPlaceholderText('Please enter your id')
        layout.addWidget(label_your_id, 0, 0)
        layout.addWidget(self.lineEdit_id, 0, 1)

        label_password = QLabel('Password:')
        self.lineEdit_password = QLineEdit()
        self.lineEdit_password.setPlaceholderText('Please enter your password')
        self.lineEdit_password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(label_password, 1, 0)
        layout.addWidget(self.lineEdit_password, 1, 1)

        label_cert_path = QLabel('Cert path:')
        self.lineEdit_cert_path = QLineEdit()
        self.lineEdit_cert_path.setPlaceholderText('Please enter your cert path')
        layout.addWidget(label_cert_path, 2, 0)
        layout.addWidget(self.lineEdit_cert_path, 2, 1)
        
        label_cert_pwd = QLabel('Cert Password:')
        self.lineEdit_cert_pwd = QLineEdit()
        self.lineEdit_cert_pwd.setPlaceholderText('Please enter your cert password')
        self.lineEdit_cert_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(label_cert_pwd, 3, 0)
        layout.addWidget(self.lineEdit_cert_pwd, 3, 1)

        label_acc = QLabel('Account:')
        self.lineEdit_acc = QLineEdit()
        self.lineEdit_acc.setPlaceholderText('Please enter your account')
        self.lineEdit_cert_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(label_acc, 4, 0)
        layout.addWidget(self.lineEdit_acc, 4, 1)

        folder_btn = QPushButton('')
        folder_btn.setIcon(QIcon('folder.png'))
        layout.addWidget(folder_btn, 2, 2)

        login_btn = QPushButton('Login')
        layout.addWidget(login_btn, 5, 0, 1, 2)

        layout_all.addLayout(layout)
        self.setLayout(layout_all)
        
        folder_btn.clicked.connect(self.showDialog)
        login_btn.clicked.connect(self.check_password)
        
        my_file = Path("./info.pkl")
        if my_file.is_file():
            with open('info.pkl', 'rb') as f:
                user_info_dict = pickle.load(f)
                self.lineEdit_id.setText(user_info_dict['id'])
                self.lineEdit_password.setText(user_info_dict['pwd'])
                self.lineEdit_cert_path.setText(user_info_dict['cert_path'])
                self.lineEdit_cert_pwd.setText(user_info_dict['cert_pwd'])
                self.lineEdit_acc.setText(user_info_dict['target_account'])


    def showDialog(self):
        # Open the file dialog to select a file
        file_path, _ = QFileDialog.getOpenFileName(self, '請選擇您的憑證檔案', 'C:\\', 'All Files (*)')

        if file_path:
            self.lineEdit_cert_path.setText(file_path)
    
    def check_password(self):
        global active_account, sdk
        msg = QMessageBox()

        fubon_id = self.lineEdit_id.text()
        fubon_pwd = self.lineEdit_password.text()
        cert_path = self.lineEdit_cert_path.text()
        cert_pwd = self.lineEdit_cert_pwd.text()
        target_account = self.lineEdit_acc.text()
        
        user_info_dict = {
            'id':fubon_id,
            'pwd':fubon_pwd,
            'cert_path':cert_path,
            'cert_pwd':cert_pwd,
            'target_account':target_account
        }      
    
        accounts = sdk.login(fubon_id, fubon_pwd, Path(cert_path).__str__(), cert_pwd)
        if accounts.is_success:
            for cur_account in accounts.data:
                if cur_account.account == target_account:
                    active_account = cur_account
                    with open('info.pkl', 'wb') as f:
                        pickle.dump(user_info_dict, f)
                    
                    self.main_app = MainApp()
                    self.main_app.show()
                    self.close()
                    
            if active_account == None:
                sdk.logout()
                msg.setWindowTitle("登入失敗")
                msg.setText("找不到您輸入的帳號")
                msg.exec()
        else:
            msg.setWindowTitle("登入失敗")
            msg.setText(accounts.message)
            msg.exec()

class Communicate(QObject):
    # 定義一個帶參數的信號
    print_log_signal = Signal(str)

class MainApp(QWidget):
    def __init__(self):
        super().__init__()

        my_icon = QIcon()
        my_icon.addFile('inventory.png')

        self.setWindowIcon(my_icon)
        self.setWindowTitle("Python庫存停損停利(教學範例，僅限現股)")
        self.resize(1200, 600)
        
        self.mutex = QMutex()
        
        # 製作上下排列layout上為庫存表，下為log資訊
        layout = QVBoxLayout()
        # 庫存表表頭
        self.table_header = ['股票名稱', '股票代號', '類別', '庫存股數', '庫存均價', '現價', '停損', '停利', '損益試算', '獲利率%']
        
        self.tablewidget = QTableWidget(0, len(self.table_header))
        self.tablewidget.setHorizontalHeaderLabels([f'{item}' for item in self.table_header])
        
        # 整個設定區layout
        layout_condition = QGridLayout()

        # 監控區layout設定
        label_monitor = QLabel('預設停損停利設定')
        label_monitor.setStyleSheet("QLabel { font-size: 24px; font-weight: bold; }")
        label_monitor.setAlignment(Qt.AlignCenter)
        layout_condition.addWidget(label_monitor, 0, 0)
        label_sl = QLabel('\t預設停損(%, 0為不預設停損):')
        layout_condition.addWidget(label_sl, 1, 0)
        self.lineEdit_default_sl = QLineEdit()
        self.lineEdit_default_sl.setText('-5')
        layout_condition.addWidget(self.lineEdit_default_sl, 1, 1)
        label_sl_post = QLabel('%')
        layout_condition.addWidget(label_sl_post, 1, 2)
        label_tp = QLabel('\t預設停利(%, 0為不預設停損):')
        layout_condition.addWidget(label_tp, 2, 0)
        self.lineEdit_default_tp = QLineEdit()
        self.lineEdit_default_tp.setText('5')
        layout_condition.addWidget(self.lineEdit_default_tp, 2, 1)
        label_tp_post = QLabel('%')
        layout_condition.addWidget(label_tp_post, 2, 2)

        # 啟動按鈕
        self.button_start = QPushButton('開始監控')
        self.button_start.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.button_start.setStyleSheet("QPushButton { font-size: 24px; font-weight: bold; }")
        layout_condition.addWidget(self.button_start, 0, 6, 3, 1)

        # 停止按鈕
        self.button_stop = QPushButton('停止監控')
        self.button_stop.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.button_stop.setStyleSheet("QPushButton { font-size: 24px; font-weight: bold; }")
        layout_condition.addWidget(self.button_stop, 0, 6, 3, 1)
        self.button_stop.setVisible(False)

        # 模擬區layout設定
        self.button_fake_buy_filled = QPushButton('fake buy filled')
        self.button_fake_sell_filled = QPushButton('fake sell filled')
        self.button_fake_websocket = QPushButton('fake websocket')

        layout_sim = QGridLayout()
        label_sim = QLabel('測試用按鈕')
        label_sim.setStyleSheet("QLabel { font-size: 24px; font-weight: bold; }")
        label_sim.setAlignment(Qt.AlignCenter)
        layout_sim.addWidget(label_sim, 0, 1)
        layout_sim.addWidget(self.button_fake_buy_filled, 1, 0)
        layout_sim.addWidget(self.button_fake_sell_filled, 1, 1)
        layout_sim.addWidget(self.button_fake_websocket, 1, 2)
        
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)

        layout.addWidget(self.tablewidget)
        layout.addLayout(layout_condition)
        layout.addLayout(layout_sim)
        layout.addWidget(self.log_text)
        self.setLayout(layout)

        self.print_log("login success, 現在使用帳號: {}".format(active_account.account))
        self.print_log("建立行情連線...")
        sdk.init_realtime() # 建立行情連線
        self.print_log("行情連線建立OK")
        self.reststock = sdk.marketdata.rest_client.stock
        self.wsstock = sdk.marketdata.websocket_client.stock

        # slot function connect
        self.button_start.clicked.connect(self.on_button_start_clicked)
        self.button_stop.clicked.connect(self.on_button_stop_clicked)

        # communicator init and slot function connect
        self.communicator = Communicate()
        self.communicator.print_log_signal.connect(self.print_log)
        
        # 初始化庫存表資訊
        self.default_sl_percent = float(self.lineEdit_default_sl.text())
        self.default_tp_percent = float(self.lineEdit_default_tp.text())

        self.inventories = {}
        self.unrealized_pnl = {}
        self.row_idx_map = {}
        self.col_idx_map = dict(zip(self.table_header, range(len(self.table_header))))
        self.epsilon = 0.0000001

        # self.stop_loss_dict = {}
        # self.take_profit_dict = {}
        
        


    # 視窗啟動時撈取對應帳號的inventories和unrealized_pnl初始化表格
    def table_init(self):
        inv_res = sdk.accounting.inventories(active_account)
        if inv_res.is_success:
            self.print_log("庫存抓取成功")
            inv_data = inv_res.data
            for inv in inv_data:
                if inv.today_qty != 0 and inv.order_type == OrderType.Stock:
                    self.inventories[(inv.stock_no, str(inv.order_type))] = inv
        else:
            self.print_log("庫存抓取失敗")
        
        self.print_log("抓取未實現損益...")
        upnl_res = sdk.accounting.unrealized_gains_and_loses(active_account)
        if upnl_res.is_success:
            self.print_log("未實現損益抓取成功")
            upnl_data = upnl_res.data
            for upnl in upnl_data:
                self.unrealized_pnl[(upnl.stock_no, str(upnl.order_type))] = upnl
        else:
            self.print_log("未實現損益抓取失敗")

        
        # 依庫存及未實現損益資訊開始填表
        for key, value in self.inventories.items():
            ticker_res = self.reststock.intraday.ticker(symbol=key[0])
            print(ticker_res['name'])
            row = self.tablewidget.rowCount()
            self.tablewidget.insertRow(row)
            self.row_idx_map[ticker_res['symbol']] = row
            for j in range(len(self.table_header)):
                item = QTableWidgetItem()
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if self.table_header[j] == '股票名稱':
                    item.setText(ticker_res['name'])
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '股票代號':
                    item.setText(ticker_res['symbol'])
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '類別':
                    item.setText(str(value.order_type).split('.')[-1])
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '庫存股數':
                    item.setText(str(value.today_qty))
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '現價':
                    item.setText(str(ticker_res['previousClose']))
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '停損':
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '停利':
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '庫存均價':
                    item.setText(str(round(self.unrealized_pnl[key].cost_price+self.epsilon, 2)))
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '損益試算':
                    cur_upnl = 0
                    if self.unrealized_pnl[key].unrealized_profit > self.unrealized_pnl[key].unrealized_loss:
                        cur_upnl = self.unrealized_pnl[key].unrealized_profit
                    else:
                        cur_upnl = -(self.unrealized_pnl[key].unrealized_loss)
                    item.setText(str(cur_upnl))
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '獲利率%':
                    cur_upnl = 0
                    if self.unrealized_pnl[key].unrealized_profit > self.unrealized_pnl[key].unrealized_loss:
                        cur_upnl = self.unrealized_pnl[key].unrealized_profit
                    else:
                        cur_upnl = -(self.unrealized_pnl[key].unrealized_loss)
                    stock_cost = value.today_qty*self.unrealized_pnl[key].cost_price
                    return_rate = cur_upnl/stock_cost*100
                    item.setText(str(round(return_rate+self.epsilon, 2))+'%')
                    self.tablewidget.setItem(row, j, item)

            
            self.print_log('庫存資訊初始化完成')

        # 調整股票名稱欄位寬度
        header = self.tablewidget.horizontalHeader()      
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        print(self.row_idx_map)
        print(self.col_idx_map)

    def on_button_start_clicked(self):
        try:
            self.default_sl_percent = float(self.lineEdit_default_sl.text())
            if self.default_sl_percent > 0:
                self.print_log("請輸入正確的監控停損(%), 範圍需小於0, 0為不預設")
                return
            elif self.default_sl_percent == 0:
                self.print_log("預設停損輸入為0, 不預設停損")
            else:
                self.print_log("預設停損"+str(self.default_sl_percent)+"%, 設定成功")
        except Exception as e:
            self.print_log("請輸入正確的監控停損(%), 範圍需小於0, 0為不預設 "+str(e))
            return
        
        try:
            self.default_tp_percent = float(self.lineEdit_default_tp.text())
            if self.default_tp_percent < 0:
                self.print_log("請輸入正確的監控停利(%), 範圍需大於0, 0為不預設")
                return
            elif self.default_tp_percent == 0:
                self.print_log("預設停利輸入為0, 不預設停利")
            else:
                self.print_log("預設停利"+str(self.default_tp_percent)+"%, 設定成功")
        except Exception as e:
            self.print_log("請輸入正確的監控停利(%), 範圍需大於0, 0為不預設 "+str(e))
            return
        
        self.print_log("開始執行監控")
        self.lineEdit_default_sl.setReadOnly(True)
        self.lineEdit_default_tp.setReadOnly(True)
        self.button_start.setVisible(False)
        self.button_stop.setVisible(True)

        self.print_log("抓取庫存...")
        self.table_init()


    def on_button_stop_clicked(self):
        self.print_log("停止執行監控")
        self.lineEdit_default_sl.setReadOnly(False)
        self.lineEdit_default_tp.setReadOnly(False)
        self.button_stop.setVisible(False)
        self.button_start.setVisible(True)
        
    # 更新最新log到QPlainTextEdit的slot function
    def print_log(self, log_info):
        self.log_text.appendPlainText(log_info)
        self.log_text.moveCursor(QTextCursor.End)

try:
    sdk = FubonSDK()
except ValueError:
    raise ValueError("請確認網路連線")
active_account = None
 
if not QApplication.instance():
    app = QApplication(sys.argv)
else:
    app = QApplication.instance()
app.setStyleSheet("QWidget{font-size: 12pt;}")
form = LoginForm()
form.show()
 
sys.exit(app.exec())

