# **Takım İsmi**

Takım 65

# Ürün İle İlgili Bilgiler

## Takım Elemanları

- Şeyma Coştur: Product Owner, Developer
- Ayşegül Kılıç: Scrum Master, Developer
- Yağmur Dedekoç : Developer
- Fırat Karataşoğlu : Developer

## Ürün İsmi

SmartFinance — Kişisel Finans & Yatırım Asistanı

## Ürün Açıklaması

- SmartFinance, kullanıcıların harcamalarını takip etmesini, kategorilere ayırmasını ve kişisel bütçe önerileri almasını sağlayan yapay zeka destekli bir finansal asistan uygulamasıdır. Kullanıcı harcamalarını manuel olarak girebilir veya banka ekstresini yükleyebilir. Sistem makine öğrenmesi ile harcamaları otomatik kategorilere ayırır, anomali tespit eder ve canlı döviz, altın, hisse verilerini takip ederek kişisel öneriler üretir.


## Ürün Özellikleri

- Harcamaları otomatik kategorilere ayırma (TF-IDF + Random Forest)
- Türkçe ve İngilizce mağaza isimlerini tanıma
- Anomali tespiti (normalden sapan harcamaları bildirme)
- Canlı döviz, altın ve hisse takibi (yfinance)
- LLM agent ile kişisel bütçe ve yatırım önerileri
- Banka ekstresi PDF okuma


## Hedef Kitle

- Kişisel bütçesini takip etmek isteyen bireyler
- Yatırım kararlarını veriye dayandırmak isteyenler
- Aylık harcamalarını analiz etmek isteyen çalışanlar ve öğrenciler
- 18-65 yaş arası kullanıcılar

## Product Backlog URL

[Miro Backlog Board](https://miro.com/app/board/uXjVH_dU7Rw=/?share_link_id=760132369792)

---

# Sprint 1

- **Backlog düzeni ve Story seçimleri**: Backlog'umuz ilk yapılacak story'lere göre düzenlenmiştir. Sprint başına tahmin edilen puan sayısını geçmeyecek şekilde sıradan seçimler yapılmaktadır. Story başına çıkan tahmin puanı, toplam puanın yarısından az tutulmuştur. 

Story'ler yapılacak işlere (task'lere) bölünmüştür. Miro Board'da gözüken kırmızı item'lar yapılacak işleri (task) gösterirken, yeşil item'lar story'leri temsil etmektedir.

- **Daily Scrum**: [DailyScrumMeetingSS_Sprint1.docx](https://github.com/user-attachments/files/29663753/DailyScrumMeetingSS_Sprint1.docx)


- **Sprint board update**: Sprint board screenshotları: 

<img width="445" height="469" alt="sprint1_started" src="https://github.com/user-attachments/assets/859828be-85b2-4b34-9612-630d47df5015" />

<img width="672" height="394" alt="sprint1_process1" src="https://github.com/user-attachments/assets/97d33678-f366-40cf-985e-e4425beafdee" />

<img width="680" height="379" alt="sprint1_process2" src="https://github.com/user-attachments/assets/ec14dfc8-4a77-4b58-8ec4-ea1e9c8fc93b" />

<img width="453" height="467" alt="sprint1_completed" src="https://github.com/user-attachments/assets/257f7fb6-ef3a-49c4-a449-536ecb6800c3" />

<img width="1635" height="930" alt="sprint1_burndown" src="https://github.com/user-attachments/assets/b7e072f9-de1f-4493-8834-9d87a1017337" />


- **Ürün Durumu**:
- Ürün Canlı link ## 🚀 Canlı Demo
[SmartFinance Dashboard](https://yzta-bootcamp-2026.onrender.com)
- Ekran görüntüleri:
<img width="949" height="556" alt="sprint1_ürünss1" src="https://github.com/user-attachments/assets/721fb487-101f-48a6-aa18-546ca097f463" />


<img width="953" height="457" alt="sprint1_ürünss2" src="https://github.com/user-attachments/assets/de0a7405-72f3-45fd-b1bd-241c769bd059" />


<img width="919" height="387" alt="sprint1_ürünss3" src="https://github.com/user-attachments/assets/6f741ba7-c5db-4ad6-b7e3-a5e8fddf7022" />


<img width="942" height="463" alt="sprint1_ürünss4" src="https://github.com/user-attachments/assets/0683e49d-3849-45d6-845b-0a9d736f11b6" />



- **Sprint Review**: 
Alınan kararlar:
  - Para birimi ayrıştırması iki farklı modülde farklı şekilde ele alındığı görülmüştür. Bu tutarsızlığın tek bir standarda bağlanması bir sonraki sprint'e aktarılmıştır.
  - Anomali tespiti özelliği, veri altyapısı hazır olmasına rağmen bu sprint kapsamına alınmamış, ilgili PBI Sprint 2'ye aktarılmıştır.
  - Çıkan ürünün çalışmasında ve testlerinde bir problem görülmemiştir; dashboard canlıya alınmış ve çalışan link sunulabilir durumdadır. Kategorilendirme modeli %99.66 doğrulukla test edilmiştir.
  - Ekstra koyulması gereken özellikler belirlenmiştir: kullanıcının kendi banka ekstresini yükleyebilmesi, anomali tespiti ve yatırımcı modu.
  - Sprint Review katılımcıları: Yağmur Dedekoç, Şeyma Coştur , Ayşegül Kılıç, Fırat Karataşoğlu

- **Sprint Retrospective:**
  - Mock veri ile paralel çalışma yaklaşımı başarılı olmuş, ekip üyeleri birbirini beklemeden ilerleyebilmiştir; bu yöntem sonraki sprintlerde de sürdürülecektir.
  - Para birimi (USD/INR) karışıklığı geç fark edilmiş, farklı modüllerde farklı çözümler üretilmiştir. Sonraki sprintte ortak kararların daha erken alınması ve modüller arası tutarlılığın planlama aşamasında netleştirilmesi gerektiği görülmüştür.
  - Tahmin puanları gözden geçirilmeli; bazı işlerin (özellikle veri temizleme ve entegrasyon) tahmin edilenden daha fazla efor gerektirdiği fark edilmiştir.
 
# Sprint 2

- **Backlog düzeni ve Story seçimleri**: Backlog'umuz ilk yapılacak story'lere göre düzenlenmiştir. Sprint başına tahmin edilen puan sayısını geçmeyecek şekilde sıradan seçimler yapılmaktadır. Story başına çıkan tahmin puanı, toplam puanın yarısından az tutulmuştur. 

Story'ler yapılacak işlere (task'lere) bölünmüştür. Miro Board'da gözüken kırmızı item'lar yapılacak işleri (task) gösterirken, yeşil item'lar story'leri temsil etmektedir.

- **Daily Scrum**: [DailyScrumMeetingSS_Sprint2.docx](https://github.com/user-attachments/files/30164187/DailyScrumMeetingSS_Sprint2.docx)


- **Sprint board update**: https://miro.com/app/board/uXjVH_dU7Rw=/?share_link_id=325036977024
- Sprint board screenshotları:
<img width="410" height="493" alt="sprint2_Not-started" src="https://github.com/user-attachments/assets/8d419d5e-ba35-475b-a11a-0d6f80457d91" />
<img width="419" height="423" alt="sprint2_In-progress1" src="https://github.com/user-attachments/assets/b7381c4f-cc5c-4920-ae1c-792f2e6d316b" />
<img width="685" height="403" alt="sprint2_In-progress2" src="https://github.com/user-attachments/assets/f963ab81-3356-4d1d-a534-5b6515dc6a7e" />
<img width="671" height="466" alt="sprint2_In-progress3" src="https://github.com/user-attachments/assets/a5e4f6a9-dd4a-4f72-abc7-d4f4d088fb60" />
<img width="410" height="366" alt="sprint2_In-progress4" src="https://github.com/user-attachments/assets/5ecdc54f-e164-4b3c-9681-f7724838569c" />
<img width="373" height="440" alt="Sprint2_Completed" src="https://github.com/user-attachments/assets/505833cc-fdc5-47e9-92db-92433127fa0e" />
<img width="1628" height="930" alt="sprint2_burndown_final" src="https://github.com/user-attachments/assets/461bf3b1-41c2-4412-a658-fccbc6094491" />

- **Ürün Durumu**:
- Ürün Canlı link ## 🚀 Canlı Demo https://yzta-bootcamp-2026.onrender.com
<img width="960" height="507" alt="sprint2_ürünss3" src="https://github.com/user-attachments/assets/955c39e1-b423-416f-9521-bf08e172ce26" />
<img width="957" height="477" alt="sprint2_ürünss2" src="https://github.com/user-attachments/assets/07267c85-3319-4462-8ddb-d3cd977a0b92" />
<img width="960" height="503" alt="sprint2_ürünss1" src="https://github.com/user-attachments/assets/e7e278e2-2361-4aaf-9456-5b1f4e4af471" />
<img width="960" height="488" alt="sprint2_ürünss4" src="https://github.com/user-attachments/assets/41f0e0c1-5403-476b-bd9c-ca8f247a4f29" />
<img width="960" height="492" alt="sprint2_ürünss8" src="https://github.com/user-attachments/assets/32e4b2f7-911d-42da-9d9e-d4bd4cb9e63e" />
<img width="957" height="329" alt="sprint2_ürünss7" src="https://github.com/user-attachments/assets/4037cfc6-ab82-4236-af1d-b418eafc38f8" />
<img width="960" height="367" alt="sprint2_ürünss6" src="https://github.com/user-attachments/assets/8d557d1e-bcca-42ab-9d25-8416abb332a8" />
<img width="959" height="486" alt="sprint2_ürünss5" src="https://github.com/user-attachments/assets/f7b64982-9695-4d34-9d44-d508a56e2e01" />
<img width="960" height="448" alt="sprint2_ürünss9" src="https://github.com/user-attachments/assets/0075d8c1-4af5-4f15-babf-f5eff49696fe" />
<img width="959" height="366" alt="sprint2_ürünss13" src="https://github.com/user-attachments/assets/126c12fd-fc70-4688-9a4e-3e8db7e944bd" />
<img width="948" height="447" alt="sprint2_ürünss12" src="https://github.com/user-attachments/assets/a62c1a47-f60c-4de6-94fb-dd32c918e9df" />
<img width="957" height="483" alt="sprint2_ürünss11" src="https://github.com/user-attachments/assets/bb232c83-bbf2-4f08-8d84-bb5f0f46a228" />
<img width="950" height="472" alt="sprint2_ürünss10" src="https://github.com/user-attachments/assets/f9ac5c35-9ec5-4551-9c6d-8a4ed9cee735" />
<img width="960" height="335" alt="sprint2_ürünss14" src="https://github.com/user-attachments/assets/6286a5bf-2e9b-49c5-9d40-b9e42d9055df" />

- **Sprint Review**: 
Alınan kararlar:
Anomali tespiti ve bütçe hesaplama mantığı geliştirilmiş, ancak bu çıktıların ortak veri dosyasına (dashboard_data.json) yazılmadığı tespit edilmiştir. Geçici çözüm olarak hesaplamalar arayüz katmanında da yapılmış, kalıcı çözümün bir sonraki sprintte tek noktada birleştirilmesine karar verilmiştir.
Veri kolon isimlerinde ekip içi tutarsızlık gözlenmiş (kontratta amount olarak belirlenen alanın farklı modüllerde farklı adlarla üretilmesi), arayüz tarafında esnek kolon eşleme ile çözülmüştür. Veri kontratının yeniden gözden geçirilmesi PBI olarak eklenmiştir.
AI agent modülü canlı LLM bağlantısıyla (Gemini API) çalışır hale getirilmiş, API anahtarı bulunmadığında devreye giren yedek cevap mekanizması sayesinde demo güvenliği sağlanmıştır.
Kullanıcı arayüzünde ekip içi referansların görünmesi sorunu tespit edilmiş, hem veri dosyası düzeltilmiş hem de arayüze kalıcı bir metin temizleme filtresi eklenmiştir.
Yatırımcı modu özelliği ekip tarafından değerlendirilmiş, kapsam netleşmediği için Product Backlog'da bekletilmesine karar verilmiştir.
Çıkan ürün canlı ortamda çalışır durumdadır; kullanıcı dosya yükleme, anomali tespiti, bütçe takibi ve doğal dil sorgu özellikleri test edilmiş, kritik bir problem görülmemiştir.
Sprint Review katılımcıları:  Yağmur Dedekoç, Şeyma Coştur , Ayşegül Kılıç, Fırat Karataşoğlu

- **Sprint Retrospective:**
- Mock veri ile paralel çalışma yaklaşımı bu sprintte de işe yaradı; modüller birbirini beklemeden geliştirildi
- Sprint 2'de kıyasla işler sprint boyunca dengeli dağıldı
- Ekip üyeleri kendi modüllerini bitirdikten sonra entegrasyon için gereken bilgiyi (fonksiyon imzası, çıktı formatı) proaktif paylaştı
- Sonraki sprint için kararlar alındı
- Veri kontratı yeniden gözden geçirilecek ve her modülün çıktısı teslim öncesi kontrata göre doğrulanacak
- Hesaplama mantıkları tek bir katmanda toplanacak, arayüz yalnızca gösterimden sorumlu olacak
- Deploy ve depo erişim yetkileri sprint başında netleştirilecek
- Kullanıcıya görünen tüm metinler teslim öncesi gözden geçirilecek

  
