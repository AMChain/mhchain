import sys
import socket
import json

import hashlib
import json
from textwrap import dedent
from time import time
from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import Flask, jsonify, request

class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions =[]
        self.nodes = set()

        # genesis
        self.new_block(prevhash='1', proof=100)
        
    def register_node(self, address):
        """
        Вносим новый узел в список узлов

        :param address: <str> адрес узла , другими словами: 'http://192.168.0.5:5000'
        :return: None
        """
        
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)
        print("Add new node: ", parsed_url.netloc)
    
    def valid_chain(self, chain):
        """
        Проверяем, является ли внесенный в блок хеш корректным

        :param chain: <list> blockchain
        :return: <bool> True если она действительна, False, если нет
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")
            # Проверьте правильность хеша блока
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Проверяем, является ли подтверждение работы корректным
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True
        
    
    def resolve_conflicts(self):
        """
        Это наш алгоритм Консенсуса, он разрешает конфликты, 
        заменяя нашу цепь на самую длинную в цепи

        :return: <bool> True, если бы наша цепь была заменена, False, если нет.
        """

        neighbours = self.nodes
        new_chain = None

        # Ищем только цепи, длиннее нашей
        max_length = len(self.chain)

        # Захватываем и проверяем все цепи из всех узлов сети
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')
            
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Проверяем, является ли длина самой длинной, а цепь - валидной
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Заменяем нашу цепь, если найдем другую валидную и более длинную
        if new_chain:
            self.chain = new_chain
            return True

        return False
        
    def proof_of_work(self, last_proof):
        """
        Простая проверка алгоритма:
         - Поиска числа p`, так как hash(pp`) содержит 4 заглавных нуля, где p - предыдущий
         - p является предыдущим доказательством, а p` - новым
 
        :param last_proof: <int>
        :return: <int>
        """
 
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
 
        return proof

    def new_block(self, proof, prevhash=None):
        # new block
        block = {
                'index': len(self.chain) + 1,
                'timestamp':time(),
                'transactions':self.current_transactions,
                'proof':proof,
                'prevhash': prevhash or self.hash(self.chain[-1]),
        }

        self.current_transactions = []

        self.chain.append(block)
        return(block)

    def new_transaction(self, sender, recipient, amount):
        self.current_transactions.append({
            'sender': sender,
            'recipient':recipient,
            'amount':amount,
        })

        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
         # sort
         block_string = json.dumps(block, sort_keys = True).encode()
         return hashlib.sha256(block_string).hexdigest()
    
    @staticmethod
    def valid_proof(last_proof, proof):
        """
        Подтверждение доказательства: Содержит ли hash(last_proof, proof) 4 заглавных нуля?
 
        :param last_proof: <int> Предыдущее доказательство
        :param proof: <int> Текущее доказательство
        :return: <bool> True, если правильно, False, если нет.
        """
 
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:2] == "12"

    @property
    def last_block(self):
        return self.chain[-1]

blockchain = Blockchain()

app = Flask(__name__)
node_identifier = str(uuid4()).replace('-','')

@app.route('/mine', methods = ['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']

    proof = blockchain.proof_of_work(last_proof)
    
    blockchain.new_transaction(
            sender="0",
            recipient=node_identifier,
            amount=1,
    )

    prevhash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, prevhash)

    response = {
            'message': "NEW BLOCK FORGED",
            'index': block['index'],
            'transactions': block['transactions'],
            'proof':block['proof'],
            'prevhash': block['prevhash'],
    }
    return jsonify(response), 200

@app.route('/tr/new', methods = ['POST'])
def new_transaction():
    """
    curl -X POST -H "Content-Type: application/json" -d '{
        "sender": "mh",
        "recipient": "fc",
        "amount": 0.005
    """

    values = request.get_json()

    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return "MISSING VALUES", 400

    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'Add trx to Block {index}'} 
    return jsonify(response), 201

@app.route('/chain', methods= ['GET'])
def full_chain():
    response = {
            'chain': blockchain.chain,
            'length': len(blockchain.chain),
    }
    return jsonify(response), 200
    
@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    
    nodes = values.get("nodes")
    if nodes is None:
        return "ERROR LIST NODES", 400
        
    for node in nodes:
        blockchain.register_node(node)
        
    response = {
        'message':'Nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

# JSON
@app.route('/save',methods=['GET'])
def save_json():
    with open('file.json', 'w') as fw:
        json.dump(blockchain.chain, fw)

    response = {
        'message':'Json file saved',
        'filename': 'file.json',
    }
    return jsonify(response), 200

# blockchain - список для записи, но с помощью json можно записывать любые объекты


# открываем файл в режиме записи (обязательно)
# файл не нужно закрывать если используется с `with`
# записываем

@app.route('/load', methods=['GET'])
def load_json():
    # открываем файл в режиме чтения
    with open('file.json', 'r') as fr:
        # читаем из файла
        blockchain.chain = json.load(fr)

    response = {
        'message':'Json file loaded',
        'filename': 'file.json',
    }
    return jsonify(response), 200

# blockchain explorer
# 

@app.route('/chain/<index>')
def get_block(index):

    index = int(index)
    response = {
        'chain': blockchain.chain[index-1],
    }
    return jsonify(response), 200


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()
 
    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }
    return jsonify(response), 200
    
if __name__ == '__main__':
    if sys.argv[1] != 'server':
        raise RuntimeError(
            f"Usage mhchain.py server [host] [port]"
        )

    host = sys.argv[2]
    port = int(sys.argv[3])
    print ('Welcome to mhchain at ',host, ':', port)
    app.run(host, port)
