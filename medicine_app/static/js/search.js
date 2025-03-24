/**
 * 의약품 검색 시스템 - 검색 관련 자바스크립트
 */
document.addEventListener('DOMContentLoaded', function() {
    // 검색 조건을 저장할 객체
    let searchTerms = {
        product_names: [],
        manufacturers: [],
        side_effects: [] 
    };
    
    // 선택된 검색 조건 UI 업데이트 함수
    function updateSelectedTerms() {
        const container = document.getElementById('selectedTermsContainer');
        const list = document.getElementById('selectedTermsList');
        
        if (!container || !list) return;
        
        list.innerHTML = '';
        
        const hasTerms = searchTerms.product_names.length > 0 || 
                        searchTerms.manufacturers.length > 0 || 
                        searchTerms.side_effects.length > 0;
        
        if (hasTerms) {
            container.style.display = 'block';
            
            // 제품명 추가
            searchTerms.product_names.forEach(term => {
                const termElem = document.createElement('div');
                termElem.className = 'selected-term';
                termElem.innerHTML = `<span class="term-type">제품명</span>${term} <span data-type="product_names" data-term="${term}">×</span>`;
                list.appendChild(termElem);
            });
            
            // 제조사 추가
            searchTerms.manufacturers.forEach(term => {
                const termElem = document.createElement('div');
                termElem.className = 'selected-term';
                termElem.innerHTML = `<span class="term-type">제조사</span>${term} <span data-type="manufacturers" data-term="${term}">×</span>`;
                list.appendChild(termElem);
            });
            
            // 부작용 추가
            searchTerms.side_effects.forEach(term => {
                const termElem = document.createElement('div');
                termElem.className = 'selected-term';
                termElem.innerHTML = `<span class="term-type">부작용</span>${term} <span data-type="side_effects" data-term="${term}">×</span>`;
                list.appendChild(termElem);
            });
        } else {
            container.style.display = 'none';
        }
    }

    // 페이지 로드 시 URL에서 검색 조건 초기화
    initSearchTermsFromURL();
    
    // URL에서 검색 조건 가져오기
    function initSearchTermsFromURL() {
        const url = new URL(window.location.href);
        const params = url.searchParams;
        
        // 제품명 파라미터 처리
        params.getAll('product_name').forEach(term => {
            if (term && !searchTerms.product_names.includes(term)) {
                searchTerms.product_names.push(term);
            }
        });
        
        // 제조사 파라미터 처리
        params.getAll('manufacturer').forEach(term => {
            if (term && !searchTerms.manufacturers.includes(term)) {
                searchTerms.manufacturers.push(term);
            }
        });
        
        // 부작용 파라미터 처리
        params.getAll('side_effect').forEach(term => {
            if (term && !searchTerms.side_effects.includes(term)) {
                searchTerms.side_effects.push(term);
            }
        });
        
        // 선택된 검색 조건 UI 업데이트
        updateSelectedTerms();
    }

    // 검색어 추가 함수
    function addSearchTerm(type, term) {
        term = term.trim();
        if (term && !searchTerms[type].includes(term)) {
            searchTerms[type].push(term);
            updateSelectedTerms();
        }
    }
    
    // 제품명 추가 버튼 이벤트
    const addProductNameBtn = document.getElementById('addProductNameBtn');
    if (addProductNameBtn) {
        addProductNameBtn.addEventListener('click', function() {
            const input = document.getElementById('productNameInput');
            addSearchTerm('product_names', input.value);
            input.value = '';
            
            const modal = bootstrap.Modal.getInstance(document.getElementById('productNameModal'));
            modal.hide();
        });
    }

    // 제조사 추가 버튼 이벤트
    const addManufacturerBtn = document.getElementById('addManufacturerBtn');
    if (addManufacturerBtn) {
        addManufacturerBtn.addEventListener('click', function() {
            const input = document.getElementById('manufacturerInput');
            addSearchTerm('manufacturers', input.value);
            input.value = '';
            
            const modal = bootstrap.Modal.getInstance(document.getElementById('manufacturerModal'));
            modal.hide();
        });
    }

    // 부작용 추가 버튼 이벤트
    const addSideEffectBtn = document.getElementById('addSideEffectBtn');
    if (addSideEffectBtn) {
        addSideEffectBtn.addEventListener('click', function() {
            const input = document.getElementById('sideEffectInput');
            addSearchTerm('side_effects', input.value);
            input.value = '';
            
            const modal = bootstrap.Modal.getInstance(document.getElementById('sideEffectModal'));
            modal.hide();
        });
    }

    // 검색 조건 삭제 이벤트
    const selectedTermsList = document.getElementById('selectedTermsList');
    if (selectedTermsList) {
        selectedTermsList.addEventListener('click', function(e) {
            if (e.target.hasAttribute('data-term')) {
                const type = e.target.getAttribute('data-type');
                const term = e.target.getAttribute('data-term');
                
                searchTerms[type] = searchTerms[type].filter(t => t !== term);
                updateSelectedTerms();
            }
        });
    }

    // 검색 결과 페이지에서 검색 조건 삭제 이벤트
    const searchTermsContainer = document.getElementById('searchTermsContainer');
    if (searchTermsContainer) {
        searchTermsContainer.addEventListener('click', function(e) {
            if (e.target.classList.contains('remove-term')) {
                const type = e.target.getAttribute('data-type');
                const term = e.target.getAttribute('data-term');
                
                // 현재 URL 가져오기
                const url = new URL(window.location.href);
                const params = url.searchParams;
                
                // 해당 검색 조건 제거
                const values = params.getAll(type);
                params.delete(type);
                
                // 제거할 조건을 제외한 나머지 조건 다시 추가
                values.forEach(value => {
                    if (value !== term) {
                        params.append(type, value);
                    }
                });
                
                // 수정된 URL로 이동
                window.location.href = url.pathname + (params.toString() ? '?' + params.toString() : '');
            }
        });
    }

    // 검색 버튼 이벤트
    const searchButton = document.getElementById('searchButton');
    if (searchButton) {
        searchButton.addEventListener('click', function() {
            // 검색 조건을 URL 파라미터로 변환
            const params = new URLSearchParams();
            
            searchTerms.product_names.forEach(term => {
                params.append('product_name', term);
            });
            
            searchTerms.manufacturers.forEach(term => {
                params.append('manufacturer', term);
            });
            
            searchTerms.side_effects.forEach(term => {
                params.append('side_effect', term);
            });
            
            // 검색 결과 페이지로 이동
            window.location.href = `/search?${params.toString()}`;
        });
    }
    
    // 초기화 버튼 이벤트
    const clearButton = document.getElementById('clearButton');
    if (clearButton) {
        clearButton.addEventListener('click', function() {
            searchTerms = {
                product_names: [],
                manufacturers: [],
                side_effects: []
            };
            updateSelectedTerms();
        });
    }

    // 검색어 입력 필드 엔터 키 이벤트 처리
    const productNameInput = document.getElementById('productNameInput');
    if (productNameInput) {
        productNameInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                document.getElementById('addProductNameBtn').click();
            }
        });
    }
    
    const manufacturerInput = document.getElementById('manufacturerInput');
    if (manufacturerInput) {
        manufacturerInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                document.getElementById('addManufacturerBtn').click();
            }
        });
    }
    
    const sideEffectInput = document.getElementById('sideEffectInput');
    if (sideEffectInput) {
        sideEffectInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                document.getElementById('addSideEffectBtn').click();
            }
        });
    }
});