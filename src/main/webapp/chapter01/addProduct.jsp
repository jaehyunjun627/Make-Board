<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>
<%@page import="java.util.ArrayList"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>addProduct</title>
<link rel="stylesheet" type="text/css" href="../css/fromcss.css" />
</head>
<body>
	<%
	request.setCharacterEncoding("utf-8");

	String productname = request.getParameter("product");
	//세션에서 리스트 가져오기(처음엔 애러/비었기떄문에)
	ArrayList<String> list = (ArrayList<String>) session.getAttribute("list");

	//맨처음 장바구니 사용시 예외처리: 리스트가 없으면 컬렉션 새로 생성

	if (list == null) {
		list = new ArrayList<String>();
		session.setAttribute("list", list);

	}

	list.add(productname);
	%>

	<div align="center">
		<h2>상품 추가 완료</h2>
		<p>
			<strong><%=productname%></strong>가(이) 장바구니에 추가되었습니다.
		</p>
		<a href="selectProduct.jsp">쇼핑 계속하기</a><br> <br> <a
			href="viewCart.jsp">장바구니 확인</a>
	</div>

</body>
</html>