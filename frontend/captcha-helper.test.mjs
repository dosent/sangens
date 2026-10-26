import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const html=readFileSync(new URL('../tools/sangens-setup/captcha.html',import.meta.url),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];

test('Помощник ждёт нажатия человека и не запускает вторую проверку одновременно',async()=>{
  let calls=0,finish;const messages=[];
  const context=vm.createContext({setTimeout,clearTimeout,window:{webkit:{messageHandlers:{captcha:{postMessage:m=>messages.push(m)}}},grecaptcha:{ready:callback=>callback(),execute:()=>{calls++;return new Promise(resolve=>finish=resolve);}}}});
  vm.runInContext(script,context);
  assert.equal(calls,0);
  vm.runInContext('sdkReady()',context);
  assert.equal(calls,0);
  vm.runInContext('beginVerification();beginVerification()',context);
  assert.equal(calls,1);
  finish('human-result');await new Promise(resolve=>setImmediate(resolve));
  assert.equal(messages.at(-1).kind,'result');assert.equal(messages.at(-1).value,'human-result');
});

test('Ошибка Google сообщается без автоповтора',async()=>{
  let calls=0;const messages=[];
  const context=vm.createContext({setTimeout,clearTimeout,window:{webkit:{messageHandlers:{captcha:{postMessage:m=>messages.push(m)}}},grecaptcha:{ready:callback=>callback(),execute:()=>{calls++;return Promise.reject(new Error('Google error'));}}}});
  vm.runInContext(script,context);vm.runInContext('beginVerification()',context);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls,1);assert.equal(messages.at(-1).kind,'error');assert.equal(messages.at(-1).value,'');
});
